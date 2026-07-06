from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langchain_google_genai import ChatGoogleGenerativeAI

from app.agent.state import AgentState, get_initial_state
from app.agent.nodes.greeting import create_greeting_node
from app.agent.nodes.info_collection import create_info_collection_node
from app.agent.nodes.qualification import create_qualification_node
from app.agent.nodes.faq import create_faq_node
from app.agent.nodes.objection_handling import create_objection_handling_node
from app.agent.nodes.meeting_booking import create_meeting_booking_node
from app.agent.nodes.human_handoff import create_human_handoff_node
from app.agent.nodes.end_conversation import create_end_conversation_node
from app.config.settings import settings


async def handle_next_node(state: AgentState) -> dict:
    return {}


def route_after_greeting(state: AgentState) -> str:
    intent = state.get("lead_intent", "unknown")
    if intent == "support":
        return "faq"
    return "info_collection"


def route_after_info_collection(state: AgentState) -> str:
    missing = state.get("missing_fields", [])
    if missing:
        return "info_collection"
    return "qualification"


def route_after_qualification(state: AgentState) -> str:
    return "handle_next"


def route_next_action(state: AgentState) -> str:
    confidence = state.get("confidence", 1.0)
    if confidence < settings.human_handoff_confidence:
        return "human_handoff"

    if state.get("human_escalated"):
        return "end"

    booking = state.get("booking_confirmed", False)
    next_action = state.get("next_action", "")

    if next_action == "end" or booking:
        return "end"

    objection_keywords = ["price", "cost", "expensive", "budget", "too much", "not sure",
                          "alternatives", "competitor", "trust", "scam", "risky", "later",
                          "need to think", "check with", "talk to my"]
    user_msgs = [m for m in state.get("conversation_history", []) if m.get("role") == "user"]
    last_user_msg = user_msgs[-1]["content"].lower() if user_msgs else ""
    has_objection = any(kw in last_user_msg for kw in objection_keywords)

    if has_objection:
        return "objection_handling"

    if next_action == "meeting_booking":
        return "meeting_booking"

    lead_status = state.get("lead_status", "")
    if lead_status in ("hot", "warm"):
        return "meeting_booking"

    return "info_collection"


def route_after_objection(state: AgentState) -> str:
    if state.get("human_escalated"):
        return "human_handoff"
    if state.get("booking_confirmed"):
        return "end"
    lead_status = state.get("lead_status", "")
    if lead_status in ("hot", "warm"):
        return "meeting_booking"
    return "info_collection"


def route_after_meeting(state: AgentState) -> str:
    if state.get("booking_confirmed"):
        return "end"
    return "meeting_booking"


def build_graph() -> CompiledStateGraph:
    model = ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        temperature=settings.gemini_temperature,
        api_key=settings.gemini_api_key,
    )

    workflow = StateGraph(AgentState)

    workflow.add_node("greeting", create_greeting_node(model))
    workflow.add_node("info_collection", create_info_collection_node(model))
    workflow.add_node("qualification", create_qualification_node(model))
    workflow.add_node("faq", create_faq_node(model))
    workflow.add_node("objection_handling", create_objection_handling_node(model))
    workflow.add_node("meeting_booking", create_meeting_booking_node(model))
    workflow.add_node("human_handoff", create_human_handoff_node(model))
    workflow.add_node("end", create_end_conversation_node(model))
    workflow.add_node("handle_next", handle_next_node)

    workflow.set_entry_point("greeting")

    workflow.add_conditional_edges(
        "greeting",
        route_after_greeting,
        {"info_collection": "info_collection", "faq": "faq"},
    )

    workflow.add_conditional_edges(
        "info_collection",
        route_after_info_collection,
        {"info_collection": "info_collection", "qualification": "qualification"},
    )

    workflow.add_conditional_edges(
        "qualification",
        route_after_qualification,
        {"handle_next": "handle_next"},
    )

    workflow.add_conditional_edges(
        "handle_next",
        route_next_action,
        {
            "info_collection": "info_collection",
            "objection_handling": "objection_handling",
            "meeting_booking": "meeting_booking",
            "human_handoff": "human_handoff",
            "faq": "faq",
            "end": "end",
        },
    )

    workflow.add_conditional_edges(
        "faq",
        route_after_info_collection,
        {"info_collection": "info_collection", "qualification": "qualification"},
    )

    workflow.add_conditional_edges(
        "objection_handling",
        route_after_objection,
        {
            "info_collection": "info_collection",
            "meeting_booking": "meeting_booking",
            "human_handoff": "human_handoff",
            "end": "end",
        },
    )

    workflow.add_conditional_edges(
        "meeting_booking",
        route_after_meeting,
        {"end": "end", "meeting_booking": "meeting_booking"},
    )

    workflow.add_edge("human_handoff", "end")
    workflow.add_edge("end", END)

    memory = MemorySaver()

    graph = workflow.compile(checkpointer=memory)
    return graph


_agent_graph: CompiledStateGraph | None = None


def get_graph() -> CompiledStateGraph:
    global _agent_graph
    if _agent_graph is None:
        _agent_graph = build_graph()
    return _agent_graph


async def run_agent(session_id: str, message: str, channel: str = "web") -> dict:
    config = {"configurable": {"thread_id": session_id}}
    initial_state = get_initial_state(session_id, channel)
    initial_state["messages"] = [HumanMessage(content=message)]

    result = await get_graph().ainvoke(initial_state, config)
    return result
