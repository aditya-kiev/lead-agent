import pytest

from langgraph.graph import END

from app.agent.graph import get_entry_point, route_after_greeting, route_after_info_collection, route_after_meeting, route_after_objection, route_after_qualification, route_next_action
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
    assert route_after_info_collection(state) == END

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


def test_get_entry_point_resumes_from_current_node():
    """Entry point must use current_node from persisted state, not hardcoded greeting."""
    state = get_initial_state("test-1")
    # First turn: current_node defaults to "greeting"
    assert get_entry_point(state) == "greeting"

    # Subsequent turn: resume from whatever the last active node was
    state["current_node"] = "info_collection"
    assert get_entry_point(state) == "info_collection"

    state["current_node"] = "meeting_booking"
    assert get_entry_point(state) == "meeting_booking"


def test_get_entry_point_falls_back_to_greeting_for_unknown_node():
    """Unknown current_node should fall back to greeting."""
    state = get_initial_state("test-1")
    state["current_node"] = "nonexistent"
    assert get_entry_point(state) == "greeting"


def test_info_collection_ends_when_missing_fields():
    """Partial info must complete in one step and route to END, not loop."""
    state = get_initial_state("test-1")
    state["missing_fields"] = ["lead_name"]
    # The graph run should end here, not loop back to info_collection
    assert route_after_info_collection(state) == END


def test_route_after_meeting_ends_when_not_confirmed():
    """Unconfirmed booking must route to END, not self-loop."""
    state = get_initial_state("test-1")
    state["booking_confirmed"] = False
    assert route_after_meeting(state) == END

    state["booking_confirmed"] = True
    assert route_after_meeting(state) == "end"


def test_route_next_action_fallback_ends():
    """Cold lead with no objection must route to END, not info_collection."""
    state = get_initial_state("test-1")
    state["confidence"] = 1.0
    state["lead_status"] = "cold"
    assert route_next_action(state) == END


def test_route_after_objection_fallback_ends():
    """Non-hot/warm lead with no escalation must route to END, not info_collection."""
    state = get_initial_state("test-1")
    state["lead_status"] = "cold"
    assert route_after_objection(state) == END


async def test_info_collection_does_not_loop_on_partial_data():
    """Simulate a full graph run with partial info — must complete in one step."""
    from unittest.mock import AsyncMock, MagicMock, patch

    mock_response = MagicMock()
    mock_response.content = '{"Name": "Alice"}'

    mock_model = MagicMock()
    mock_model.ainvoke = AsyncMock(return_value=mock_response)

    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(return_value={
        "missing_fields": ["company_name", "budget", "timeline", "problem_statement", "industry"],
        "conversation_history": [{"role": "assistant", "content": "What's your company name?"}],
        "current_node": "info_collection",
    })
    mock_graph.checkpointer = MagicMock()
    mock_graph.checkpointer.adelete_thread = AsyncMock()

    with patch("app.agent.graph.ChatGoogleGenerativeAI", return_value=mock_model), \
         patch("app.agent.graph.get_entry_point", return_value="info_collection"), \
         patch("app.agent.graph.memory_service.load_state", new_callable=AsyncMock, return_value=None), \
         patch("app.agent.graph.get_graph", return_value=mock_graph):

        from app.agent.graph import run_agent
        result = await run_agent("test-partial", "My name is Alice")

    # Must have exactly one assistant reply (follow-up question), not a loop
    history = result.get("conversation_history", [])
    assistant_msgs = [m for m in history if m.get("role") == "assistant"]
    assert len(assistant_msgs) == 1, f"Expected 1 assistant reply, got {len(assistant_msgs)}: {history}"


def test_gemini_timeout_is_configured():
    """ChatGoogleGenerativeAI must be constructed with a timeout so hanging
    Gemini calls raise an exception instead of blocking forever."""
    from unittest.mock import MagicMock, patch
    with patch("app.agent.graph.ChatGoogleGenerativeAI") as mock_cls:
        mock_cls.return_value = MagicMock()
        from app.agent.graph import build_graph
        build_graph()
    _, kwargs = mock_cls.call_args
    assert "timeout" in kwargs, "ChatGoogleGenerativeAI must have a timeout kwarg"
    assert kwargs["timeout"] > 0, "timeout must be a positive number (seconds)"
