import pytest

from app.agent.graph import route_after_greeting, route_after_info_collection, route_after_qualification, route_next_action
from app.agent.state import get_initial_state


def test_state_initialization():
    state = get_initial_state("test-123")
    assert state["session_id"] == "test-123"
    assert state["lead_name"] is None
    assert state["company_name"] is None
    assert state["qualification_score"] is None
    assert state["booking_confirmed"] is False
    assert state["human_escalated"] is False
    assert state["current_node"] == "greeting"
    assert state["conversation_stage"] == "greeting"


def test_route_after_greeting():
    state = get_initial_state("test-1")
    assert route_after_greeting(state) == "info_collection"

    state["lead_intent"] = "support"
    assert route_after_greeting(state) == "faq"


def test_route_after_info_collection():
    state = get_initial_state("test-1")
    state["missing_fields"] = ["lead_name", "budget"]
    assert route_after_info_collection(state) == "info_collection"

    state["missing_fields"] = []
    assert route_after_info_collection(state) == "qualification"


def test_route_after_qualification():
    state = get_initial_state("test-1")
    assert route_after_qualification(state) == "handle_next"


def test_route_next_action_hot_lead():
    state = get_initial_state("test-1")
    state["lead_status"] = "hot"
    assert route_next_action(state) == "meeting_booking"


def test_route_next_action_booking():
    state = get_initial_state("test-1")
    state["booking_confirmed"] = True
    assert route_next_action(state) == "end"


def test_route_next_action_human_escalated():
    state = get_initial_state("test-1")
    state["human_escalated"] = True
    assert route_next_action(state) == "end"


def test_route_next_action_low_confidence():
    state = get_initial_state("test-1")
    state["confidence"] = 0.1
    assert route_next_action(state) == "human_handoff"


def test_route_next_action_objection_handling():
    state = get_initial_state("test-1")
    state["objection_type"] = "pricing"
    assert route_next_action(state) == "objection_handling"

    state["objection_type"] = "timing"
    assert route_next_action(state) == "objection_handling"


def test_route_next_action_objection_takes_precedence_over_hot():
    """Objection routing should take precedence over hot-lead routing."""
    state = get_initial_state("test-1")
    state["objection_type"] = "trust"
    state["lead_status"] = "hot"
    assert route_next_action(state) == "objection_handling"


async def test_greeting_node_skips_for_returning_user():
    """The greeting node must not re-enter for returning users mid-conversation."""
    state = get_initial_state("test-1")
    state["conversation_history"] = [{"role": "assistant", "content": "Hello!"}]
    state["conversation_stage"] = "collecting"
    state["current_node"] = "info_collection"

    from unittest.mock import MagicMock, AsyncMock
    from app.agent.nodes.greeting import create_greeting_node

    mock_model = MagicMock()
    mock_model.ainvoke = AsyncMock(
        side_effect=Exception("should not be called for returning user")
    )
    node_fn = create_greeting_node(mock_model)
    result = await node_fn(state)

    assert result == {}, "Greeting node must return empty dict for returning users"


def test_state_default_values():
    state = get_initial_state("session-001", "email")
    assert state["channel"] == "email"
    assert state["session_id"] == "session-001"
    assert state["lead_intent"] is None
    assert state["iteration_count"] == 0
    assert state["confidence"] == 1.0
    assert state["current_question"] is None
