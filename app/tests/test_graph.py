import pytest

from app.agent.graph import route_entry, route_after_greeting, route_after_info_collection, route_after_qualification, compute_missing_fields
from app.agent.state import get_initial_state


def _populate(state: dict, fields: dict):
    for k, v in fields.items():
        state[k] = v


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


def test_route_entry_new_session():
    state = get_initial_state("test-1")
    assert route_entry(state) == "greeting"


def test_route_entry_resume_with_missing():
    state = get_initial_state("test-1")
    _populate(state, {"lead_name": "John", "conversation_history": [{"role": "assistant", "content": "Hi"}]})
    assert route_entry(state) == "info_collection"


def test_route_entry_all_fields_present():
    state = get_initial_state("test-1")
    _populate(state, {
        "lead_name": "John",
        "company_name": "Acme",
        "industry": "tech",
        "budget": 50000,
        "timeline": "immediate",
        "problem_statement": "Need help",
        "conversation_history": [{"role": "assistant", "content": "Hi"}],
    })
    assert route_entry(state) == "qualification"


def test_route_entry_already_qualified():
    state = get_initial_state("test-1")
    _populate(state, {
        "lead_status": "hot",
        "conversation_history": [{"role": "assistant", "content": "Hi"}],
    })
    assert route_entry(state) == "end_conversation"


def test_route_after_greeting():
    state = get_initial_state("test-1")
    state["conversation_history"] = [{"role": "user", "content": "Hi"}]
    assert route_after_greeting(state) == "info_collection"

    _populate(state, {
        "lead_name": "John",
        "company_name": "Acme",
        "industry": "tech",
        "budget": 50000,
        "timeline": "immediate",
        "problem_statement": "Need help",
    })
    assert route_after_greeting(state) == "qualification"


def test_route_after_info_collection():
    state = get_initial_state("test-1")
    assert route_after_info_collection(state) == "__end__"

    _populate(state, {
        "lead_name": "John",
        "company_name": "Acme",
        "industry": "tech",
        "budget": 50000,
        "timeline": "immediate",
        "problem_statement": "Need help",
    })
    assert route_after_info_collection(state) == "qualification"


def test_route_after_qualification():
    state = get_initial_state("test-1")
    assert route_after_qualification(state) == "__end__"


def test_compute_missing_fields():
    state = get_initial_state("test-1")
    missing = compute_missing_fields(state)
    assert "lead_name" in missing
    assert "budget" in missing

    _populate(state, {
        "lead_name": "John",
        "company_name": "Acme",
        "industry": "tech",
        "budget": 50000,
        "timeline": "immediate",
        "problem_statement": "Need help",
    })
    assert compute_missing_fields(state) == []


def test_state_default_values():
    state = get_initial_state("session-001", "email")
    assert state["channel"] == "email"
    assert state["session_id"] == "session-001"
    assert state["lead_intent"] is None
    assert state["iteration_count"] == 0
    assert state["confidence"] == 1.0
    assert state["current_question"] is None
