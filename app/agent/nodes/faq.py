from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.agent.prompts.templates import FAQ_SYSTEM_PROMPT
from app.agent.state import AgentState


def create_faq_node(model: ChatGoogleGenerativeAI):
    async def faq_node(state: AgentState) -> dict:
        user_message = state["messages"][-1].content if state["messages"] else ""

        response = await model.ainvoke([
            SystemMessage(content=FAQ_SYSTEM_PROMPT.format(
                company_name="our company",
                input=user_message,
            )),
            HumanMessage(content=user_message),
        ])

        return {
            "messages": [AIMessage(content=response.content)],
            "conversation_history": [{"role": "assistant", "content": response.content}],
            "current_node": "faq",
            "next_action": "collect_info",
        }

    return faq_node
