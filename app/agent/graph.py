import logging

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

logger = logging.getLogger(__name__)
_node_logger = logging.getLogger("graph.node")


FIELD_PRIORITY = [
    "lead_name",
    "company_name",
    "industry",
    "problem_statement",
    "budget",
    "timeline",
]


def compute_missing_fields(state: AgentState) -> list[str]:
    missing = []
    for field in FIELD_PRIORITY:
        val = state.get(field)
        if field == "budget":
            if val is None:
                missing.append(field)
        elif not val:
            missing.append(field)
    return missing


def route_entry(state: AgentState) -> str:
    history = state.get("conversation_history", [])
    stage = state.get("conversation_stage", "greeting")
    _node_logger.info("ROUTE entry: stage=%s history_len=%s lead_status=%s",
                      stage, len(history), state.get("lead_status"))

    if state.get("lead_status") is not None:
        return "end_conversation"

    if not history:
        return "greeting"

    missing = compute_missing_fields(state)
    if missing:
        return "info_collection"

    if stage in ("greeting", "collecting"):
        return "qualification"

    return "end_conversation"


def route_after_greeting(state: AgentState) -> str:
    missing = compute_missing_fields(state)
    _node_logger.info("ROUTE after_greeting: missing=%s", missing)
    if missing:
        return "info_collection"
    return "qualification"


def route_after_info_collection(state: AgentState) -> str:
    missing = compute_missing_fields(state)
    _node_logger.info("ROUTE after_info_collection: missing=%s", missing)
    if missing:
        return END
    return "qualification"


def route_after_qualification(state: AgentState) -> str:
    _node_logger.info("ROUTE after_qualification: lead_status=%s", state.get("lead_status"))
    return END


def build_graph() -> CompiledStateGraph:
    logger.info("GRAPH: building graph with model=%s", settings.gemini_model)

    model = ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        temperature=settings.gemini_temperature,
        api_key=settings.gemini_api_key,
    )
    logger.info("GRAPH: ChatGoogleGenerativeAI created")

    workflow = StateGraph(AgentState)

    workflow.add_node("greeting", create_greeting_node(model))
    workflow.add_node("info_collection", create_info_collection_node(model))
    workflow.add_node("qualification", create_qualification_node(model))
    workflow.add_node("faq", create_faq_node(model))
    workflow.add_node("objection_handling", create_objection_handling_node(model))
    workflow.add_node("meeting_booking", create_meeting_booking_node(model))
    workflow.add_node("human_handoff", create_human_handoff_node(model))
    workflow.add_node("end_conversation", create_end_conversation_node(model))

    workflow.set_conditional_entry_point(
        route_entry,
        {
            "greeting": "greeting",
            "info_collection": "info_collection",
            "qualification": "qualification",
            "end_conversation": "end_conversation",
        },
    )

    workflow.add_conditional_edges(
        "greeting",
        route_after_greeting,
        {"info_collection": "info_collection", "qualification": "qualification"},
    )

    workflow.add_conditional_edges(
        "info_collection",
        route_after_info_collection,
        {"qualification": "qualification", END: END},
    )

    workflow.add_conditional_edges(
        "qualification",
        route_after_qualification,
        {END: END},
    )

    workflow.add_edge("faq", END)
    workflow.add_edge("objection_handling", END)
    workflow.add_edge("meeting_booking", END)
    workflow.add_edge("human_handoff", END)
    workflow.add_edge("end_conversation", END)

    memory = MemorySaver()

    graph = workflow.compile(checkpointer=memory)
    logger.info("GRAPH: graph compiled OK")
    return graph


_agent_graph: CompiledStateGraph | None = None


def get_graph() -> CompiledStateGraph:
    global _agent_graph
    if _agent_graph is None:
        _agent_graph = build_graph()
    return _agent_graph


async def run_agent(session_id: str, message: str, channel: str = "web") -> dict:
    logger.info("RUN_AGENT: session_id=%s message=%s channel=%s", session_id, message[:50], channel)
    config = {"configurable": {"thread_id": session_id}}

    existing = await get_graph().aget_state(config)
    if existing and existing.values:
        logger.info("RUN_AGENT: resuming session, existing keys=%s", list(existing.values.keys()))
        turn_input = {
            "messages": [HumanMessage(content=message)],
        }
    else:
        logger.info("RUN_AGENT: new session, building initial state")
        turn_input = get_initial_state(session_id, channel)
        turn_input["messages"] = [HumanMessage(content=message)]

    result = await get_graph().ainvoke(turn_input, config)
    logger.info("RUN_AGENT: ainvoke completed, result keys=%s lead_status=%s stage=%s",
                list(result.keys()), result.get("lead_status"), result.get("conversation_stage"))
    return result
