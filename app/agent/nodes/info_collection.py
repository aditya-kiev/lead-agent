import json
import logging
import re

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.agent.prompts.templates import INFO_COLLECTION_SYSTEM_PROMPT, EXTRACTION_PROMPT
from app.agent.state import AgentState
from app.agent.nodes.helpers import safe_text

logger = logging.getLogger("graph.node.info_collection")

_FIELD_MAP = {
    "Name": "lead_name",
    "Company": "company_name",
    "Industry": "industry",
    "Budget": "budget",
    "Timeline": "timeline",
    "Problem": "problem_statement",
}

FIELD_PRIORITY = [
    "lead_name",
    "company_name",
    "industry",
    "problem_statement",
    "budget",
    "timeline",
]


def _extract_json(text: str) -> dict | None:
    text = text.strip()
    json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if json_match:
        text = json_match.group(1).strip()
    try:
        result = json.loads(text)
        return result if isinstance(result, dict) else None
    except (json.JSONDecodeError, TypeError):
        return None


def _compute_missing(merged: dict) -> list[str]:
    missing = []
    for field in FIELD_PRIORITY:
        val = merged.get(field)
        if field == "budget":
            if val is None:
                missing.append(field)
        elif not val:
            missing.append(field)
    return missing


def create_info_collection_node(model: ChatGoogleGenerativeAI):
    async def info_collection_node(state: AgentState) -> dict:
        user_msgs = [m for m in state.get("messages", []) if isinstance(m, HumanMessage)]
        raw_last = user_msgs[-1].content if user_msgs else ""
        user_message = safe_text(raw_last)

        lead_name = state.get("lead_name")
        company_name = state.get("company_name")
        industry = state.get("industry")
        budget = state.get("budget")
        timeline = state.get("timeline")
        problem_statement = state.get("problem_statement")

        logger.info(
            "NODE info_collection ENTERED: session=%s user_msg=%s",
            state.get("session_id"), user_message[:60],
        )

        conv_text = "\n".join(
            f"{m['role']}: {m['content']}" for m in state.get("conversation_history", [])
        )

        logger.info("NODE info_collection: LLM call 1/1 (extraction)")
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
        extraction_text = safe_text(extraction_response.content)
        logger.info("NODE info_collection: extraction response=%s", extraction_text[:120])

        updates = {}
        extracted = _extract_json(extraction_text)
        if extracted is not None:
            for label, state_field in _FIELD_MAP.items():
                val = extracted.get(label) or extracted.get(state_field)
                if val:
                    updates[state_field] = val
            logger.info("NODE info_collection: updates=%s", updates)
        else:
            logger.info("NODE info_collection: no valid JSON extracted")

        merged = {
            "lead_name": updates.get("lead_name", lead_name),
            "company_name": updates.get("company_name", company_name),
            "industry": updates.get("industry", industry),
            "budget": updates.get("budget", budget),
            "timeline": updates.get("timeline", timeline),
            "problem_statement": updates.get("problem_statement", problem_statement),
        }

        missing_fields = _compute_missing(merged)
        logger.info("NODE info_collection: missing_fields=%s", missing_fields)

        if not missing_fields:
            logger.info("NODE info_collection: all fields present, routing to qualification")
            return {
                **updates,
                "missing_fields": [],
                "next_action": "qualify",
                "current_node": "info_collection",
                "conversation_stage": "qualifying",
                "current_question": None,
            }

        first_missing = missing_fields[0]
        logger.info("NODE info_collection: asking one question about '%s'", first_missing)

        response = await model.ainvoke([
            SystemMessage(content=INFO_COLLECTION_SYSTEM_PROMPT.format(
                lead_name=merged["lead_name"] or "not provided",
                company_name=merged["company_name"] or "not provided",
                industry=merged["industry"] or "not provided",
                budget=merged["budget"] or "not provided",
                timeline=merged["timeline"] or "not provided",
                problem_statement=merged["problem_statement"] or "not provided",
                missing_fields=[first_missing],
                input=user_message,
            )),
            HumanMessage(content=user_message),
        ])
        response_text = safe_text(response.content)
        logger.info("NODE info_collection: response=%s", response_text[:80])

        return {
            **updates,
            "messages": [AIMessage(content=response.content)],
            "conversation_history": [{"role": "assistant", "content": response_text}],
            "missing_fields": missing_fields,
            "current_node": "info_collection",
            "next_action": "collect_info",
            "conversation_stage": "collecting",
            "current_question": first_missing,
        }

    return info_collection_node
