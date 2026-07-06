from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.agent.prompts.templates import QUALIFICATION_SYSTEM_PROMPT
from app.agent.state import AgentState
from app.agent.tools.lead_scoring import compute_lead_score
from app.models.schemas import IntentType, LeadScoreIn


def create_qualification_node(model: ChatOpenAI):
    async def qualification_node(state: AgentState) -> dict:
        score_data = LeadScoreIn(
            budget=state.get("budget"),
            timeline=state.get("timeline"),
            industry=state.get("industry"),
            problem_statement=state.get("problem_statement"),
            intent=IntentType(state.get("lead_intent", "unknown")),
        )

        score_result = compute_lead_score(score_data)

        context = "\n".join(
            f"{m['role']}: {m['content']}" for m in state.get("conversation_history", [])
        ) if state.get("conversation_history") else ""

        llm_response = await model.ainvoke([
            SystemMessage(content=QUALIFICATION_SYSTEM_PROMPT.format(
                lead_name=state.get("lead_name", "Unknown"),
                company_name=state.get("company_name", "Unknown"),
                industry=state.get("industry", "Unknown"),
                budget=state.get("budget", "Unknown"),
                timeline=state.get("timeline", "Unknown"),
                problem_statement=state.get("problem_statement", "Unknown"),
                lead_intent=state.get("lead_intent", "unknown"),
            )),
            HumanMessage(content=f"Lead context:\n{context}\n\nEvaluate this lead."),
        ])

        return {
            "qualification_score": score_result.score,
            "lead_status": score_result.status.value,
            "messages": [AIMessage(content=llm_response.content)],
            "conversation_history": [{"role": "assistant", "content": llm_response.content}],
            "current_node": "qualification",
            "next_action": "handle_next",
        }

    return qualification_node
