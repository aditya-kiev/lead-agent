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


def test_route_after_greeting():
    state = get_initial_state("test-1")
    assert route_after_greeting(state) == "info_collection"

    state["lead_intent"] = "support"
    assert route_after_greeting(state) == "faq"


def test_route_after_info_collection():
    state = get_initial_state("test-1")
    state["missing_fields"] = ["name", "budget"]
    assert route_after_info_collection(state) == "info_collection"

    state["missing_fields"] = []
    assert route_after_info_collection(state) == "qualification"


def test_route_after_qualification():
    state = get_initial_state("test-1")
    assert route_after_qualification(state) == "handle_next"


def test_route_next_action_hot_lead():
    state = get_initial_state("test-1")
    state["lead_status"] = "hot"
    route = route_next_action(state)
    assert route in ("meeting_booking", "info_collection")


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


def test_state_default_values():
    state = get_initial_state("session-001", "email")
    assert state["channel"] == "email"
    assert state["session_id"] == "session-001"
    assert state["lead_intent"] is None
    assert state["iteration_count"] == 0
    assert state["confidence"] == 1.0
