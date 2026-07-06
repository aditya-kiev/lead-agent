from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.crud import get_conversation, update_conversation, create_conversation
from app.database.session import async_session_factory


class ConversationMemory:
    async def save_state(self, session_id: str, state: dict) -> None:
        async with async_session_factory() as db_session:
            existing = await get_conversation(db_session, session_id)
            if not existing:
                await create_conversation(db_session, session_id)

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

    async def load_state(self, session_id: str) -> dict | None:
        async with async_session_factory() as db_session:
            lead = await get_conversation(db_session, session_id)
            if not lead:
                return None
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


memory_service = ConversationMemory()
