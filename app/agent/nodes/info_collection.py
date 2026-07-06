import json

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.agent.prompts.templates import INFO_COLLECTION_SYSTEM_PROMPT, EXTRACTION_PROMPT
from app.agent.state import AgentState


def create_info_collection_node(model: ChatOpenAI):
    async def info_collection_node(state: AgentState) -> dict:
        user_message = state["messages"][-1].content if state["messages"] else ""

        lead_name = state.get("lead_name")
        company_name = state.get("company_name")
        industry = state.get("industry")
        budget = state.get("budget")
        timeline = state.get("timeline")
        problem_statement = state.get("problem_statement")

        missing_fields = []
        if not lead_name:
            missing_fields.append("name")
        if not company_name:
            missing_fields.append("company name")
        if not industry:
            missing_fields.append("industry")
        if budget is None:
            missing_fields.append("budget")
        if not timeline:
            missing_fields.append("timeline")
        if not problem_statement:
            missing_fields.append("problem statement")

        conv_text = "\n".join(
            f"{m['role']}: {m['content']}" for m in state.get("conversation_history", [])
        )

        extraction_response = await model.ainvoke([
            SystemMessage(content=EXTRACTION_PROMPT.format(
                lead_name=lead_name or "",
                company_name=company_name or "",
                industry=industry or "",
                budget=budget or "",
                timeline=timeline or "",
                problem_statement=problem_statement or "",
                messages=conv_text,
            )),
            HumanMessage(content="Extract any new information from the conversation."),
        ])

        updates = {}
        try:
            extracted = json.loads(extraction_response.content)
            if isinstance(extracted, dict):
                for field in ["lead_name", "company_name", "industry", "budget", "timeline", "problem_statement"]:
                    if field in extracted and extracted[field]:
                        updates[field] = extracted[field]
        except (json.JSONDecodeError, TypeError):
            pass

        if not missing_fields:
            return {
                **updates,
                "missing_fields": [],
                "next_action": "qualify",
                "current_node": "info_collection",
            }

        response = await model.ainvoke([
            SystemMessage(content=INFO_COLLECTION_SYSTEM_PROMPT.format(
                lead_name=updates.get("lead_name", lead_name or "not provided"),
                company_name=updates.get("company_name", company_name or "not provided"),
                industry=updates.get("industry", industry or "not provided"),
                budget=updates.get("budget", budget or "not provided"),
                timeline=updates.get("timeline", timeline or "not provided"),
                problem_statement=updates.get("problem_statement", problem_statement or "not provided"),
                missing_fields=missing_fields,
                input=user_message,
            )),
            HumanMessage(content=user_message),
        ])

        return {
            **updates,
            "messages": [AIMessage(content=response.content)],
            "conversation_history": [{"role": "assistant", "content": response.content}],
            "missing_fields": missing_fields,
            "current_node": "info_collection",
            "next_action": "collect_info" if missing_fields else "qualify",
        }

    return info_collection_node
