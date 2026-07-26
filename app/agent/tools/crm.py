import asyncio
import json
import logging

import httpx

from app.config.settings import settings

logger = logging.getLogger(__name__)

_CRM_LEADS: dict[str, dict] = {}


def update_crm(session_id: str, lead_data: dict) -> dict:
    _CRM_LEADS[session_id] = {
        **_CRM_LEADS.get(session_id, {}),
        **lead_data,
        "session_id": session_id,
        "updated_at": __import__("datetime").datetime.utcnow().isoformat(),
    }

    # Fire outbound webhook (non-blocking, best-effort)
    if settings.crm_webhook_url:
        asyncio.ensure_future(_fire_webhook(_CRM_LEADS[session_id]))

    return _CRM_LEADS[session_id]


async def _fire_webhook(payload: dict, max_retries: int = 3) -> None:
    """POST lead data to the configured webhook URL, with retry on failure."""
    headers = {"Content-Type": "application/json"}
    if settings.crm_webhook_secret:
        headers["X-Webhook-Secret"] = settings.crm_webhook_secret

    backoff = [1, 3, 9]
    last_exc = None

    for attempt in range(1, max_retries + 1):
        try:
            resp = await httpx.AsyncClient(timeout=10.0).post(
                settings.crm_webhook_url,
                headers=headers,
                content=json.dumps(payload, default=str),
            )
            if resp.is_success:
                logger.info(
                    "_fire_webhook: OK session=%s attempt=%s/%s",
                    payload.get("session_id"), attempt, max_retries,
                )
                return

            logger.warning(
                "_fire_webhook: status=%s attempt=%s/%s session=%s",
                resp.status_code, attempt, max_retries,
                payload.get("session_id"),
            )
            if resp.status_code < 500:
                return  # Non-retryable client error, give up
        except Exception as e:
            last_exc = e
            logger.warning(
                "_fire_webhook: exception attempt=%s/%s session=%s: %s",
                attempt, max_retries, payload.get("session_id"), e,
            )

        if attempt < max_retries:
            await asyncio.sleep(backoff[attempt - 1])

    logger.error(
        "_fire_webhook: failed after %s attempts session=%s",
        max_retries, payload.get("session_id"),
    )


def get_crm_lead(session_id: str) -> dict | None:
    return _CRM_LEADS.get(session_id)
