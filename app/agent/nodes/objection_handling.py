from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.agent.prompts.templates import OBJECTION_DETECTION_PROMPT, OBJECTION_HANDLING_SYSTEM_PROMPT
from app.agent.state import AgentState


def create_objection_handling_node(model: ChatGoogleGenerativeAI):
    async def objection_handling_node(state: AgentState) -> dict:
        user_message = state["messages"][-1].content if state["messages"] else ""

        detection_response = await model.ainvoke([
            SystemMessage(content=OBJECTION_DETECTION_PROMPT.format(input=user_message)),
            HumanMessage(content="What objection type is this?"),
        ])

        objection_type = "none"
        for ot in ["pricing", "timing", "trust", "competition", "need", "authority"]:
            if ot in detection_response.content.lower():
                objection_type = ot
                break

        if objection_type == "none":
            return {
                "objection_type": None,
                "next_action": "collect_info",
                "current_node": "objection_handling",
            }

        response = await model.ainvoke([
            SystemMessage(content=OBJECTION_HANDLING_SYSTEM_PROMPT.format(
                objection_type=objection_type,
                lead_name=state.get("lead_name", "there"),
                company_name=state.get("company_name", "your company"),
                industry=state.get("industry", "your industry"),
                budget=state.get("budget", "not specified"),
                timeline=state.get("timeline", "not specified"),
                problem_statement=state.get("problem_statement", "not specified"),
                input=user_message,
            )),
            HumanMessage(content=user_message),
        ])

        return {
            "messages": [AIMessage(content=response.content)],
            "conversation_history": [{"role": "assistant", "content": response.content}],
            "objection_type": objection_type,
            "current_node": "objection_handling",
            "next_action": "collect_info",
            "confidence": state.get("confidence", 1.0) - 0.05,
        }

    return objection_handling_node
