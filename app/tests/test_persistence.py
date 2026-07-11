from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.graph import run_agent


async def test_persistence_merges_saved_state_into_initial_state():
    """run_agent merges persisted lead fields from memory_service into turn_input."""
    persisted = {
        "lead_name": "Alice",
        "company_name": "Acme Corp",
        "industry": "technology",
        "budget": 50000.0,
        "timeline": "immediate",
        "problem_statement": "Need a CRM solution",
        "qualification_score": 0.75,
        "lead_status": "hot",
        "booking_confirmed": True,
        "meeting_time": "2026-07-10T14:00:00",
        "conversation_history": [
            {"role": "assistant", "content": "Great, let me ask you a few questions."},
        ],
        "conversation_stage": "collecting",
        "current_node": "info_collection",
        "human_escalated": False,
    }

    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(return_value={})
    mock_graph.checkpointer = MagicMock()
    mock_graph.checkpointer.adelete_thread = AsyncMock()

    with patch("app.agent.graph.memory_service.load_state", new_callable=AsyncMock) as mock_load:
        mock_load.return_value = persisted
        with patch("app.agent.graph.get_graph", return_value=mock_graph) as mock_get_graph:
            await run_agent("test-persist-session", "Hello again")

    call_input = mock_graph.ainvoke.call_args[0][0]
    assert call_input.get("lead_name") == "Alice"
    assert call_input.get("company_name") == "Acme Corp"
    assert call_input.get("industry") == "technology"
    assert call_input.get("budget") == 50000.0
    assert call_input.get("lead_status") == "hot"
    assert call_input.get("booking_confirmed") is True
    # run_agent appends the current user message to the loaded history
    expected_history = persisted["conversation_history"] + [
        {"role": "user", "content": "Hello again"},
    ]
    assert call_input.get("conversation_history") == expected_history
    assert call_input.get("conversation_stage") == "collecting"
    assert call_input.get("current_node") == "info_collection"


async def test_persistence_new_lead_starts_with_defaults():
    """A fresh session with no persisted data uses get_initial_state defaults."""
    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(return_value={})
    mock_graph.checkpointer = MagicMock()
    mock_graph.checkpointer.adelete_thread = AsyncMock()

    with patch("app.agent.graph.memory_service.load_state", new_callable=AsyncMock) as mock_load:
        mock_load.return_value = None
        with patch("app.agent.graph.get_graph", return_value=mock_graph):
            await run_agent("test-new-session", "Hi")

    call_input = mock_graph.ainvoke.call_args[0][0]
    assert call_input.get("lead_name") is None
    assert call_input.get("company_name") is None
    assert call_input.get("lead_status") is None
    assert call_input.get("booking_confirmed") is False


async def test_conversation_history_records_user_message_on_returning_turn():
    """Regression test: a lead's message on turn 2+ must appear in
    conversation_history, not just the bot's replies."""
    persisted = {
        "conversation_history": [
            {"role": "user", "content": "Hi there"},
            {"role": "assistant", "content": "Hello! How can I help?"},
        ],
        "conversation_stage": "collecting",
        "current_node": "info_collection",
    }

    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(return_value={})
    mock_graph.checkpointer = MagicMock()
    mock_graph.checkpointer.adelete_thread = AsyncMock()

    with patch("app.agent.graph.memory_service.load_state", new_callable=AsyncMock) as mock_load:
        mock_load.return_value = persisted
        with patch("app.agent.graph.get_graph", return_value=mock_graph):
            await run_agent("test-returning", "My budget is 50k")

    # The user message must be in conversation_history before the graph runs
    # (the reducer merges node responses, but we verify the upstream write here)
    call_input = mock_graph.ainvoke.call_args[0][0]
    history = call_input.get("conversation_history", [])
    assert any(
        m["role"] == "user" and m["content"] == "My budget is 50k"
        for m in history
    ), f"User message not found in input conversation_history: {history}"


async def test_double_call_does_not_duplicate_conversation_history():
    """Regression test: two sequential run_agent() calls with the same
    session_id must NOT duplicate conversation_history.

    Root cause: ``get_graph()`` caches a single ``MemorySaver`` for the
    process lifetime, ``conversation_history`` uses ``operator.add``
    (appending on top of checkpointed state), and ``run_agent()`` re-feeds
    the full Postgres-reloaded history on every turn.  Without deleting the
    checkpoint first, the reducer concatenates checkpoint history + fresh
    input history → duplicates.

    The fix deletes the checkpoint (``adelete_thread``) before each call so
    the graph starts fresh from the Postgres-reconstituted ``turn_input``.
    """
    from langgraph.graph import END, StateGraph
    from langgraph.checkpoint.memory import MemorySaver

    from app.agent.state import AgentState

    # ---- minimal graph with a real MemorySaver and operator.add reducer ----

    async def _passthrough(state):
        return {"current_node": "passthrough"}

    workflow = StateGraph(AgentState)
    workflow.add_node("passthrough", _passthrough)
    workflow.set_entry_point("passthrough")
    workflow.add_edge("passthrough", END)
    test_graph = workflow.compile(checkpointer=MemorySaver())

    # ---- in-memory Postgres simulation ----
    store: dict = {}

    async def _fake_save(session_id, state):
        store[session_id] = state

    async def _fake_load(session_id):
        return store.get(session_id)

    with patch("app.agent.graph.get_graph", return_value=test_graph), \
         patch("app.agent.graph.memory_service.save_state", _fake_save), \
         patch("app.agent.graph.memory_service.load_state", _fake_load):

        # ---- Turn 1 ----
        result1 = await run_agent("dup-test", "Hello")
        # webhook.py calls save_state after run_agent completes
        await _fake_save("dup-test", result1)
        hist1 = result1.get("conversation_history", [])
        assert len(hist1) == 1, (
            f"Turn 1: expected 1 entry, got {len(hist1)}: {hist1}"
        )
        assert hist1[0]["role"] == "user"
        assert hist1[0]["content"] == "Hello"

        # ---- Turn 2 (same session_id) ----
        result2 = await run_agent("dup-test", "What's your pricing?")
        await _fake_save("dup-test", result2)
        hist2 = result2.get("conversation_history", [])

        # Without the checkpoint-deletion fix, the operator.add reducer
        # would concatenate the old checkpoint's history with the freshly
        # Postgres-reloaded history, producing 3+ entries here.
        # With the fix the graph starts clean and yields exactly 2 entries.
        assert len(hist2) == 2, (
            f"Turn 2: expected 2 entries (no duplicates), got {len(hist2)}: {hist2}"
        )
        assert hist2[0] == {"role": "user", "content": "Hello"}
        assert hist2[1] == {"role": "user", "content": "What's your pricing?"}
