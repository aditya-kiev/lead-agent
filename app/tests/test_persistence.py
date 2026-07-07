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
    assert call_input.get("conversation_history") == persisted["conversation_history"]


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
