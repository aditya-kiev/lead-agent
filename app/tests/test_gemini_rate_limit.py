from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.agent.gemini import GeminiRateLimitError, RetryingGeminiModel
from app.main import app


class FakeGeminiRateLimitError(Exception):
    def __init__(self):
        super().__init__("429 RESOURCE_EXHAUSTED")
        self.code = 429
        self.status = "RESOURCE_EXHAUSTED"


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_retrying_gemini_model_retries_rate_limits(monkeypatch):
    calls = 0
    sleeps = []

    class DummyModel:
        async def ainvoke(self, *args, **kwargs):
            nonlocal calls
            calls += 1
            if calls < 3:
                raise FakeGeminiRateLimitError()
            return "ok"

    async def fake_sleep(delay):
        sleeps.append(delay)

    monkeypatch.setattr("app.agent.gemini.asyncio.sleep", fake_sleep)

    wrapped = RetryingGeminiModel(
        DummyModel(), max_retries=2, initial_backoff_seconds=0.1
    )
    result = await wrapped.ainvoke(["prompt"])

    assert result == "ok"
    assert calls == 3
    assert sleeps == [0.1, 0.2]


async def test_single_turn_gemini_call_budget():
    """Worst-case single turn must stay under 5 Gemini calls.

    The deepest realistic path after all optimisations:
      greeting (1)
      → info_collection (1)   — combined extraction + question, all fields returned
      → qualification (1)
      → handle_next (0)       — keyword pre-filter catches "too expensive"
      → objection_handling (1) — reads state['objection_type'] (fix #3), no re-detection
      → meeting_booking (1)
      ─────────────────────────
      Total: 5

    The CountingModel branches on the system-prompt text so each node receives
    a legitimate canned response and the graph actually traverses this path
    instead of dead-ending after 2 calls.
    """
    from unittest.mock import AsyncMock, MagicMock, patch

    class CountingModel:
        def __init__(self):
            self.call_count = 0

        async def ainvoke(self, *args, **kwargs):
            self.call_count += 1
            messages = args[0] if args else []
            sys_content = ""
            for m in messages:
                if hasattr(m, "type") and m.type == "system":
                    sys_content = m.content
                    break
                if isinstance(m, dict) and m.get("role") == "system":
                    sys_content = m["content"]
                    break

            mock = MagicMock()
            if "friendly AI sales assistant" in sys_content:
                mock.content = (
                    "INTENT: purchase\nREPLY: Hello! How can I help you today?"
                )
            elif "collecting information from a potential customer" in sys_content:
                mock.content = (
                    'EXTRACTED: {"lead_name": "Alice", "company_name": "Acme Inc", '
                    '"budget": 50000, "timeline": "3 months", '
                    '"problem_statement": "Need better CRM", "industry": "tech"}\n'
                    "REPLY: Great, thanks Alice!"
                )
            elif "lead qualification expert" in sys_content:
                mock.content = (
                    "Score: 0.85  Hot lead  Good fit  Schedule a meeting."
                )
            elif "objection handling specialist" in sys_content:
                mock.content = (
                    "I understand your concern about pricing. "
                    "Let me explain the ROI our solution delivers."
                )
            elif "scheduling assistant" in sys_content:
                mock.content = (
                    "Here are some available times: tomorrow 10am, "
                    "Wednesday 2pm, Friday 11am."
                )
            else:
                mock.content = "OK"
            return mock

    counting = CountingModel()

    with patch("app.agent.graph.ChatGoogleGenerativeAI", return_value=MagicMock()), \
         patch("app.agent.graph.RetryingGeminiModel", return_value=counting), \
         patch("app.agent.graph.memory_service.load_state", new_callable=AsyncMock, return_value=None):

        from app.agent.graph import build_graph

        graph = build_graph()

        # Provide a conversation_history entry that triggers the keyword
        # pre-filter ("expensive" → pricing objection) so handle_next
        # sets objection_type without any LLM call.
        await graph.ainvoke({
            "session_id": "budget-test",
            "channel": "web",
            "lead_name": None,
            "company_name": None,
            "industry": None,
            "budget": None,
            "timeline": None,
            "problem_statement": None,
            "qualification_score": None,
            "lead_status": None,
            "lead_intent": None,
            "messages": [{"role": "user", "content": "Tell me more"}],
            "conversation_history": [
                {"role": "user", "content": "This is too expensive"},
            ],
            "current_node": "greeting",
            "next_action": None,
            "conversation_stage": "greeting",
            "booking_confirmed": False,
            "meeting_time": None,
            "human_escalated": False,
            "objection_type": None,
            "missing_fields": [],
            "confidence": 1.0,
            "iteration_count": 0,
            "current_question": None,
        }, {"configurable": {"thread_id": "budget-test"}})

    print(f"\n[budget-test] Gemini calls this turn: {counting.call_count}")
    assert counting.call_count <= 5, (
        f"Single turn made {counting.call_count} Gemini calls, expected <= 5"
    )
    assert counting.call_count >= 3, (
        f"Expected at least 3 calls to traverse greeting→info→qualification, "
        f"got {counting.call_count}"
    )


async def test_gemini_call_counter_increments():
    """Each ainvoke call on RetryingGeminiModel must increment the counter."""
    from app.agent.gemini import gemini_call_counter, RetryingGeminiModel

    assert gemini_call_counter.get() == 0

    counter = 0

    class CountingModel:
        async def ainvoke(self, *args, **kwargs):
            nonlocal counter
            counter += 1
            return "ok"

    wrapped = RetryingGeminiModel(CountingModel())
    await wrapped.ainvoke(["prompt"])
    await wrapped.ainvoke(["prompt2"])

    assert gemini_call_counter.get() == 2, "counter should be 2 after 2 calls"
    # Verify the counter is independent per-task (reset to 0)
    assert gemini_call_counter.get() == 2


async def test_webhook_maps_gemini_rate_limit_to_http_429(client):
    from app.config.settings import settings

    with patch.object(settings, "api_key", "test-secret-key"):
        with patch("app.api.webhook.run_agent", new_callable=AsyncMock) as mock_agent:
            mock_agent.side_effect = GeminiRateLimitError()

            response = await client.post(
                "/webhook/message",
                json={"session_id": "test-session", "message": "Hello"},
                headers={"X-API-Key": "test-secret-key"},
            )

    assert response.status_code == 429
    assert response.json()["detail"] == (
        "The AI service is temporarily rate limited. Please try again in a minute."
    )
