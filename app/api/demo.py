import logging
import time
import uuid

from fastapi import APIRouter, HTTPException, Request

from app.config.settings import settings
from app.services.demo_tokens import issue_demo_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/demo", tags=["demo"])

_local_hits: dict[str, list[float]] = {}


async def _rate_limited(ip: str) -> bool:
    window = 3600
    limit = 20
    now = time.time()
    hits = [t for t in _local_hits.get(ip, []) if now - t < window]
    hits.append(now)
    _local_hits[ip] = hits
    return len(hits) > limit


@router.post("/token")
async def get_demo_token(request: Request):
    ip = request.client.host if request.client else "unknown"
    if await _rate_limited(ip):
        raise HTTPException(
            status_code=429,
            detail="Too many demo sessions from this address. Try again later.",
        )

    session_id = f"demo-{uuid.uuid4().hex[:8]}"
    token, expires_at = issue_demo_token(session_id)
    return {"session_id": session_id, "token": token, "expires_at": expires_at}
