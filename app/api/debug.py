import logging

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import verify_api_key
from app.agent.graph import get_graph
from app.models.schemas import DebugStateOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/debug", tags=["debug"])


@router.get("/state/{session_id}", response_model=DebugStateOut)
async def get_debug_state(session_id: str, _auth: None = Depends(verify_api_key)) -> DebugStateOut:
    config = {"configurable": {"thread_id": session_id}}
    state = await get_graph().aget_state(config)
    if not state or not state.values:
        raise HTTPException(status_code=404, detail="Session not found")

    values = state.values
    return DebugStateOut(
        session_id=values.get("session_id", session_id),
        lead_name=values.get("lead_name"),
        company_name=values.get("company_name"),
        industry=values.get("industry"),
        budget=values.get("budget"),
        timeline=values.get("timeline"),
        problem_statement=values.get("problem_statement"),
        lead_status=values.get("lead_status"),
        qualification_score=values.get("qualification_score"),
        missing_fields=values.get("missing_fields", []),
        conversation_stage=values.get("conversation_stage", "unknown"),
        next_action=values.get("next_action"),
        current_question=values.get("current_question"),
        conversation_history_len=len(values.get("conversation_history", [])),
    )
