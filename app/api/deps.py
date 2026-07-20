from fastapi import Header, HTTPException, Request

from app.agent.gemini import demo_rpm_limit
from app.config.settings import settings
from app.services.demo_tokens import verify_demo_token


async def verify_api_key(
    request: Request,
    x_api_key: str | None = Header(None),
    x_demo_token: str | None = Header(None),
) -> None:
    # Master key path (real integrations, your own CRM/webhook callers)
    if settings.api_key and x_api_key == settings.api_key:
        return

    # Demo token path (static demo HTML) — set lower RPM limit for Gemini
    if x_demo_token:
        session_id = None
        try:
            body = await request.json()
            session_id = body.get("session_id")
        except Exception:
            pass
        if session_id is None:
            session_id = request.path_params.get("session_id")

        if session_id and verify_demo_token(x_demo_token, session_id):
            demo_rpm_limit.set(settings.demo_token_rpm_limit)
            return

    # No key configured → allow (local dev)
    if not settings.api_key:
        return

    raise HTTPException(status_code=401, detail="Invalid or missing API key")
