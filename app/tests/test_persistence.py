import pytest
from unittest.mock import AsyncMock, patch

from app.agent.graph import run_agent


async def test_persistence_merges_saved_state_into_initial_state():
    """Regression test: run_agent must merge persisted lead fields into initial state.

    Simulates two sequential calls:
      1) First call populates lead_name / company_name / etc.; save_state persists them.
      2) Second call loads that persisted state via load_state and merges it into
         get_initial_state(), so the graph sees the existing lead data instead of None.
    """
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

    with patch("app.agent.graph.memory_service.load_state", new_callable=AsyncMock) as mock_load:
        mock_load.return_value = persisted
        result = await run_agent("test-persist-session", "Hello again")

    assert result.get("lead_name") == "Alice"
    assert result.get("company_name") == "Acme Corp"
    assert result.get("industry") == "technology"
    assert result.get("budget") == 50000.0
    assert result.get("lead_status") == "hot"
    assert result.get("booking_confirmed") is True


async def test_persistence_new_lead_starts_with_defaults():
    """A fresh session with no persisted data should use get_initial_state defaults."""
    with patch("app.agent.graph.memory_service.load_state", new_callable=AsyncMock) as mock_load:
        mock_load.return_value = None
        result = await run_agent("test-new-session", "Hi")

    assert result.get("lead_name") is None
    assert result.get("company_name") is None
    assert result.get("lead_status") is None
