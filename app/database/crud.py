from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import LeadConversation


async def create_conversation(session: AsyncSession, session_id: str) -> LeadConversation:
    lead = LeadConversation(session_id=session_id)
    session.add(lead)
    await session.flush()
    return lead


async def get_conversation(session: AsyncSession, session_id: str) -> LeadConversation | None:
    result = await session.execute(select(LeadConversation).where(LeadConversation.session_id == session_id))
    return result.scalar_one_or_none()


async def update_conversation(session: AsyncSession, session_id: str, **kwargs) -> LeadConversation | None:
    stmt = (
        update(LeadConversation)
        .where(LeadConversation.session_id == session_id)
        .values(**kwargs)
        .returning(LeadConversation)
    )
    result = await session.execute(stmt)
    await session.commit()
    return result.scalar_one_or_none()
