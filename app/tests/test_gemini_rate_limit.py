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


@pytest.mark.asyncio
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
