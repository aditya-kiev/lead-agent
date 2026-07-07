from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.agent.prompts.templates import HUMAN_HANDOFF_SYSTEM_PROMPT
from app.agent.state import AgentState
from app.config.settings import settings


def create_human_handoff_node(model: ChatGoogleGenerativeAI):
    async def human_handoff_node(state: AgentState) -> dict:
        user_message = state["messages"][-1].content if state["messages"] else ""

        response = await model.ainvoke([
            SystemMessage(content=HUMAN_HANDOFF_SYSTEM_PROMPT.format(
                confidence=state.get("confidence", 0.0),
                threshold=settings.human_handoff_confidence,
                lead_name=state.get("lead_name", "Unknown"),
                company_name=state.get("company_name", "Unknown"),
                industry=state.get("industry", "Unknown"),
                lead_status=state.get("lead_status", "Unknown"),
                qualification_score=state.get("qualification_score", "N/A"),
                input=user_message,
            )),
            HumanMessage(content=user_message),
        ])

        return {
            "messages": [AIMessage(content=response.content)],
            "conversation_history": [{"role": "assistant", "content": response.content}],
            "human_escalated": True,
            "current_node": "human_handoff",
            "next_action": "end",
        }

    return human_handoff_node
