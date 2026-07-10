import logging

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.agent.prompts.templates import GREETING_SYSTEM_PROMPT, INTENT_DETECTION_PROMPT
from app.agent.state import AgentState

logger = logging.getLogger("graph.node.greeting")


def _safe_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                parts.append(item.get("text", ""))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    return str(content)


def create_greeting_node(model: ChatGoogleGenerativeAI):
    async def greeting_node(state: AgentState) -> dict:
        # Returning user guard: if conversation_history exists, this is not a new session.
        # Skip the greeting entirely so we don't re-greet mid-conversation.
        if state.get("conversation_history"):
            logger.debug("greeting_node: returning user, skipping")
            return {}

        user_msgs = [m for m in state.get("messages", []) if isinstance(m, HumanMessage)]
        raw_last = user_msgs[-1].content if user_msgs else ""
        user_message = _safe_text(raw_last)
        logger.info("NODE greeting ENTERED: session=%s user_msg=%s",
                    state.get("session_id"), user_message[:50])

        logger.info("NODE greeting: LLM call 1/2 (intent detection)")
        intent_response = await model.ainvoke([
            SystemMessage(content=INTENT_DETECTION_PROMPT.format(input=user_message)),
            HumanMessage(content="Detect the intent from the above message."),
        ])
        logger.info("NODE greeting: LLM call 1/2 response=%s", str(intent_response.content)[:100])

        known_info = {
            k: v for k, v in {
                "name": state.get("lead_name"),
                "company": state.get("company_name"),
                "industry": state.get("industry"),
            }.items() if v
        }

        logger.info("NODE greeting: LLM call 2/2 (greeting generation)")
        response = await model.ainvoke([
            SystemMessage(content=GREETING_SYSTEM_PROMPT.format(
                company_name="our company",
                lead_status=state.get("lead_status", "new"),
                known_info=str(known_info) if known_info else "none yet",
            )),
            HumanMessage(content=user_message),
        ])
        logger.info("NODE greeting: LLM call 2/2 response=%s", str(response.content)[:100])

        intent_text = _safe_text(intent_response.content).strip().lower()
        lead_intent = "unknown"
        for intent in ["purchase", "information", "support", "partnership"]:
            if intent in intent_text:
                lead_intent = intent
                break

        logger.info("NODE greeting EXIT: session=%s lead_intent=%s",
                    state.get("session_id"), lead_intent)
        return {
            "messages": [AIMessage(content=response.content)],
            "conversation_history": [
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": _safe_text(response.content)},
            ],
            "lead_intent": lead_intent,
            "current_node": "greeting",
            "next_action": "collect_info",
            "conversation_stage": "collecting",
        }

    return greeting_node
