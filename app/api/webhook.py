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
    try:
        result = await run_agent(session_id, "Hi, I'm interested in your services.", payload.channel)
        await memory_service.save_state(session_id, result)

        last_message = ""
        if result.get("conversation_history"):
            for msg in reversed(result["conversation_history"]):
                if msg.get("role") == "assistant":
                    last_message = msg["content"]
                    break

        return StartConversationOut(
            session_id=session_id,
            message=last_message or "Hello! How can I help you today?",
            lead_status=result.get("lead_status"),
        )
    except Exception as e:
        logger.exception("Failed to start conversation")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/message", response_model=MessageOut)
async def handle_message(payload: MessageIn) -> MessageOut:
    try:
        result = await run_agent(payload.session_id, payload.message, payload.channel)
        await memory_service.save_state(payload.session_id, result)

        last_message = ""
        if result.get("conversation_history"):
            for msg in reversed(result["conversation_history"]):
                if msg.get("role") == "assistant":
                    last_message = msg["content"]
                    break

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
        logger.exception("Failed to process message")
        raise HTTPException(status_code=500, detail=str(e))
