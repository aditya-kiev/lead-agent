import uuid
import logging

from fastapi import APIRouter, HTTPException

from app.agent.graph import run_agent
from app.models.schemas import (
    MessageIn,
    MessageOut,
    StartConversationIn,
    StartConversationOut,
)
from app.services.memory import memory_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["webhook"])


@router.post("/start", response_model=StartConversationOut)
async def start_conversation(payload: StartConversationIn) -> StartConversationOut:
    session_id = payload.session_id or str(uuid.uuid4())
    logger.info("=== WEBHOOK /start ENTERED === session_id=%s", session_id)
    try:
        logger.info("WEBHOOK: calling run_agent(session_id=%s)", session_id)
        result = await run_agent(session_id, "Hi, I'm interested in your services.", payload.channel)
        logger.info("WEBHOOK: run_agent returned, keys=%s", list(result.keys()))

        logger.info("WEBHOOK: calling memory_service.save_state")
        try:
            await memory_service.save_state(session_id, result)
            logger.info("WEBHOOK: save_state OK")
        except Exception as db_err:
            logger.warning("WEBHOOK: save_state failed (DB unavailable?): %s", db_err)

        last_message = ""
        if result.get("conversation_history"):
            for msg in reversed(result["conversation_history"]):
                if msg.get("role") == "assistant":
                    last_message = msg["content"]
                    break

        logger.info("WEBHOOK: returning StartConversationOut")
        return StartConversationOut(
            session_id=session_id,
            message=last_message or "Hello! How can I help you today?",
            lead_status=result.get("lead_status"),
        )
    except Exception as e:
        logger.exception("WEBHOOK: Failed to start conversation")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/message", response_model=MessageOut)
async def handle_message(payload: MessageIn) -> MessageOut:
    logger.info("=== WEBHOOK /message ENTERED === session_id=%s", payload.session_id)
    try:
        logger.info("WEBHOOK: calling run_agent(session_id=%s, message=%s)", payload.session_id, payload.message[:50])
        result = await run_agent(payload.session_id, payload.message, payload.channel)
        logger.info("WEBHOOK: run_agent returned, keys=%s", list(result.keys()))

        logger.info("WEBHOOK: calling memory_service.save_state")
        try:
            await memory_service.save_state(payload.session_id, result)
            logger.info("WEBHOOK: save_state OK")
        except Exception as db_err:
            logger.warning("WEBHOOK: save_state failed (DB unavailable?): %s", db_err)

        last_message = ""
        if result.get("conversation_history"):
            for msg in reversed(result["conversation_history"]):
                if msg.get("role") == "assistant":
                    last_message = msg["content"]
                    break

        logger.info("WEBHOOK: returning MessageOut")
        return MessageOut(
            session_id=payload.session_id,
            reply=last_message or "I understand. Let me help you with that.",
            lead_status=result.get("lead_status"),
            booking_confirmed=result.get("booking_confirmed", False),
            meeting_time=result.get("meeting_time"),
            human_escalated=result.get("human_escalated", False),
            next_action=result.get("next_action"),
        )
    except Exception as e:
        logger.exception("WEBHOOK: Failed to process message")
        raise HTTPException(status_code=500, detail=str(e))
