import logging

from fastapi import APIRouter, HTTPException

from app.database.crud import get_conversation
from app.database.session import async_session_factory
from app.models.schemas import ConversationHistoryOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/conversation", tags=["conversation"])


@router.get("/{session_id}", response_model=ConversationHistoryOut)
async def get_conversation_history(session_id: str) -> ConversationHistoryOut:
    async with async_session_factory() as db_session:
        lead = await get_conversation(db_session, session_id)
        if not lead:
            raise HTTPException(status_code=404, detail="Conversation not found")

        return ConversationHistoryOut(
            session_id=lead.session_id,
            lead_name=lead.lead_name,
            company_name=lead.company_name,
            industry=lead.industry,
            budget=lead.budget,
            timeline=lead.timeline,
            problem_statement=lead.problem_statement,
            qualification_score=lead.qualification_score,
            lead_status=lead.lead_status,
            booking_confirmed=lead.booking_confirmed,
            meeting_time=lead.meeting_time,
            human_escalated=lead.human_escalated,
            conversation_history=lead.conversation_history,
            created_at=lead.created_at,
            updated_at=lead.updated_at,
        )
