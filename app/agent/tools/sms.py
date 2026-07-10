import logging
from datetime import datetime, timezone

from app.config.settings import settings

logger = logging.getLogger(__name__)

# In-memory stub for local dev without Twilio credentials
_stub_sms_log: list[dict] = []


def send_sms(to: str, body: str) -> dict:
    """Send an SMS via Twilio, or fall back to an in-memory stub when credentials
    are absent (local dev).

    Trial Twilio accounts can only deliver to verified numbers (up to 5).
    Unverified numbers will receive the SMS silently dropped by Twilio's sandbox
    — this is a Twilio trial limitation, not a bug in this application.
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

    try:
        from twilio.rest import Client

        client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        message = client.messages.create(
            body=body,
            from_=settings.twilio_from_number,
            to=to,
        )
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
