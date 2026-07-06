from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.agent.prompts.templates import GREETING_SYSTEM_PROMPT, INTENT_DETECTION_PROMPT
from app.agent.state import AgentState


def create_greeting_node(model: ChatOpenAI):
    async def greeting_node(state: AgentState) -> dict:
        user_message = state["messages"][-1].content if state["messages"] else ""

        intent_response = await model.ainvoke([
            SystemMessage(content=INTENT_DETECTION_PROMPT.format(input=user_message)),
            HumanMessage(content="Detect the intent from the above message."),
        ])

        known_info = {
            k: v for k, v in {
                "name": state.get("lead_name"),
                "company": state.get("company_name"),
                "industry": state.get("industry"),
            }.items() if v
        }

        response = await model.ainvoke([
            SystemMessage(content=GREETING_SYSTEM_PROMPT.format(
                company_name="our company",
                lead_status=state.get("lead_status", "new"),
                known_info=str(known_info) if known_info else "none yet",
            )),
            HumanMessage(content=user_message),
        ])

        intent_text = intent_response.content.strip().lower()
        lead_intent = "unknown"
        for intent in ["purchase", "information", "support", "partnership"]:
            if intent in intent_text:
                lead_intent = intent
                break

        return {
            "messages": [AIMessage(content=response.content)],
            "conversation_history": [
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": response.content},
            ],
            "lead_intent": lead_intent,
            "current_node": "greeting",
            "next_action": "collect_info",
        }

    return greeting_node
