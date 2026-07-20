import base64
import hashlib
import hmac
import time

from app.config.settings import settings


def _sign(payload: str) -> str:
    return hmac.new(
        settings.demo_token_secret.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()


def issue_demo_token(session_id: str) -> tuple[str, int]:
    expires_at = int(time.time()) + settings.demo_token_ttl_seconds
    payload = f"{session_id}.{expires_at}"
    sig = _sign(payload)
    raw = f"{payload}.{sig}"
    token = base64.urlsafe_b64encode(raw.encode()).decode()
    return token, expires_at


def verify_demo_token(token: str, session_id: str) -> bool:
    try:
        raw = base64.urlsafe_b64decode(token.encode()).decode()
        parts = raw.split(".")
        if len(parts) != 3:
            return False
        tok_session_id, expires_at_str, sig = parts
        if tok_session_id != session_id:
            return False
        if int(expires_at_str) < int(time.time()):
            return False
        expected_sig = _sign(f"{tok_session_id}.{expires_at_str}")
        return hmac.compare_digest(sig, expected_sig)
    except Exception:
        return False
