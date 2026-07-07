import logging

from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import LeadConversation

logger = logging.getLogger(__name__)


async def create_conversation(session: AsyncSession, session_id: str) -> LeadConversation:
    logger.info("CRUD create_conversation: session_id=%s", session_id)
    lead = LeadConversation(session_id=session_id)
    session.add(lead)
    await session.flush()
    logger.info("CRUD create_conversation: OK id=%s", lead.id)
    return lead


async def get_conversation(session: AsyncSession, session_id: str) -> LeadConversation | None:
    logger.info("CRUD get_conversation: session_id=%s", session_id)
    result = await session.execute(select(LeadConversation).where(LeadConversation.session_id == session_id))
    lead = result.scalar_one_or_none()
    logger.info("CRUD get_conversation: found=%s", lead is not None)
    return lead


async def update_conversation(session: AsyncSession, session_id: str, **kwargs) -> LeadConversation | None:
    logger.info("CRUD update_conversation: session_id=%s kwargs=%s", session_id, list(kwargs.keys()))
    stmt = (
        update(LeadConversation)
        .where(LeadConversation.session_id == session_id)
        .values(**kwargs)
        .returning(LeadConversation)
    )
    result = await session.execute(stmt)
    await session.commit()
    lead = result.scalar_one_or_none()
    logger.info("CRUD update_conversation: OK lead=%s", lead is not None)
    return lead
