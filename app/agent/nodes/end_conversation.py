from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.agent.prompts.templates import END_CONVERSATION_PROMPT
from app.agent.state import AgentState

from app.agent.tools.crm import update_crm


def create_end_conversation_node(model: ChatGoogleGenerativeAI):
    async def end_conversation_node(state: AgentState) -> dict:
        user_message = state["messages"][-1].content if state["messages"] else ""

        lead_data = {
            k: state.get(k) for k in [
                "lead_name", "company_name", "industry", "budget", "timeline",
                "problem_statement", "qualification_score", "lead_status",
                "meeting_time", "booking_confirmed", "human_escalated",
            ]
        }
        update_crm(state["session_id"], lead_data)

        response = await model.ainvoke([
            SystemMessage(content=END_CONVERSATION_PROMPT.format(
                lead_name=state.get("lead_name", "there"),
                company_name=state.get("company_name", "your company"),
                lead_status=state.get("lead_status", "new"),
                booking_confirmed=state.get("booking_confirmed", False),
                human_escalated=state.get("human_escalated", False),
                input=user_message,
            )),
            HumanMessage(content=user_message),
        ])

        return {
            "messages": [AIMessage(content=response.content)],
            "conversation_history": [{"role": "assistant", "content": response.content}],
            "current_node": "end",
            "next_action": None,
        }

    return end_conversation_node
