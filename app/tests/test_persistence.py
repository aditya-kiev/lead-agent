from unittest.mock import AsyncMock, MagicMock, patch

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
