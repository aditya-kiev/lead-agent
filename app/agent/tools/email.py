import logging

import httpx

from app.config.settings import settings

logger = logging.getLogger(__name__)

_EMAIL_LOG: list[dict] = []


def send_email(to: str, subject: str, body: str) -> dict:
    sent_at = __import__("datetime").datetime.utcnow().isoformat()
    email_record = {
        "to": to,
        "subject": subject,
        "body": body,
        "sent_at": sent_at,
        "status": "sent",
    }

    # Always log locally (debug endpoint depends on this)
    _EMAIL_LOG.append(email_record)

    # Real Resend API call
    if not settings.resend_api_key:
        logger.debug("send_email: RESEND_API_KEY not set, skipping real send")
        return email_record

    try:
        resp = httpx.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {settings.resend_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "from": settings.resend_from_email,
                "to": [to],
                "subject": subject,
                "text": body,
            },
            timeout=15.0,
        )
        if resp.is_success:
            logger.info("send_email: Resend OK to=%s subject=%s", to, subject)
        else:
            logger.warning(
                "send_email: Resend failed status=%s body=%s", resp.status_code, resp.text
            )
            email_record["status"] = "failed"
    except Exception as e:
        logger.exception("send_email: Resend exception to=%s: %s", to, e)
        email_record["status"] = "failed"

    return email_record


def get_email_log() -> list[dict]:
    return list(_EMAIL_LOG)
