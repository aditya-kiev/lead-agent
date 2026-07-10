import asyncio
import logging
from datetime import datetime, timezone

from app.config.settings import settings

logger = logging.getLogger(__name__)

_stub_sms_log: list[dict] = []


async def send_sms(to: str, body: str) -> dict:
    """Send an SMS via Twilio, or fall back to an in-memory stub when credentials
    are absent (local dev).

    Trial Twilio accounts can only deliver to verified numbers (up to 5).
    The blocking Twilio SDK call is offloaded to a thread via ``asyncio.to_thread``.
    """
    now = datetime.now(timezone.utc).isoformat()

    if not settings.twilio_account_sid:
        logger.debug("sms stub: to=%s body=%s", to, body[:60])
        entry = {
            "sid": f"stub-{len(_stub_sms_log)}",
            "status": "sent",
            "to": to,
            "body": body,
            "sent_at": now,
        }
        _stub_sms_log.append(entry)
        return entry

    def _send():
        from twilio.rest import Client
        client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        return client.messages.create(
            body=body,
            from_=settings.twilio_from_number,
            to=to,
        )

    try:
        message = await asyncio.to_thread(_send)
        logger.debug("sms sent: sid=%s to=%s status=%s", message.sid, to, message.status)
        return {
            "sid": message.sid,
            "status": message.status,
            "to": to,
            "body": body,
            "sent_at": now,
        }
    except Exception as e:
        logger.warning("sms failed: %s", e)
        return {
            "sid": None,
            "status": "failed",
            "to": to,
            "body": body,
            "sent_at": now,
            "error": str(e),
        }


def get_stub_sms_log() -> list[dict]:
    return _stub_sms_log.copy()
