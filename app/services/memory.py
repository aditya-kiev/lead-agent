import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.crud import get_conversation, update_conversation, create_conversation
from app.database.session import async_session_factory

logger = logging.getLogger(__name__)


class ConversationMemory:
    async def save_state(self, session_id: str, state: dict) -> None:
        logger.info("MEMORY save_state ENTERED: session_id=%s", session_id)
        try:
            async with async_session_factory() as db_session:
                logger.info("MEMORY: DB session created")
                existing = await get_conversation(db_session, session_id)
                logger.info("MEMORY: existing=%s", existing is not None)
                if not existing:
                    logger.info("MEMORY: creating new conversation")
                    await create_conversation(db_session, session_id)
                    logger.info("MEMORY: created OK")

                logger.info("MEMORY: updating conversation")
                await update_conversation(
                    db_session,
                    session_id,
                    lead_name=state.get("lead_name"),
                    company_name=state.get("company_name"),
                    industry=state.get("industry"),
                    budget=state.get("budget"),
                    timeline=state.get("timeline"),
                    problem_statement=state.get("problem_statement"),
                    qualification_score=state.get("qualification_score"),
                    lead_status=state.get("lead_status"),
                    booking_confirmed=state.get("booking_confirmed", False),
                    meeting_time=state.get("meeting_time"),
                    conversation_history=state.get("conversation_history"),
                    human_escalated=state.get("human_escalated", False),
                )
                logger.info("MEMORY save_state EXIT: OK")
        except Exception as e:
            logger.warning("MEMORY save_state FAILED: %s", str(e), exc_info=True)
            raise

    async def load_state(self, session_id: str) -> dict | None:
        logger.info("MEMORY load_state ENTERED: session_id=%s", session_id)
        try:
            async with async_session_factory() as db_session:
                lead = await get_conversation(db_session, session_id)
                if not lead:
                    logger.info("MEMORY load_state: not found")
                    return None
                logger.info("MEMORY load_state: found lead=%s", lead.session_id)
                return {
                    "lead_name": lead.lead_name,
                    "company_name": lead.company_name,
                    "industry": lead.industry,
                    "budget": lead.budget,
                    "timeline": lead.timeline,
                    "problem_statement": lead.problem_statement,
                    "qualification_score": lead.qualification_score,
                    "lead_status": lead.lead_status,
                    "booking_confirmed": lead.booking_confirmed,
                    "meeting_time": lead.meeting_time.isoformat() if lead.meeting_time else None,
                    "conversation_history": lead.conversation_history or [],
                    "human_escalated": lead.human_escalated,
                }
        except Exception as e:
            logger.warning("MEMORY load_state FAILED: %s", str(e))
            raise


memory_service = ConversationMemory()
