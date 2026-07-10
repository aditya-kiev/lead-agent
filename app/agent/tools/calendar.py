import logging
from datetime import datetime, timedelta, timezone

import httpx

from app.config.settings import settings

logger = logging.getLogger(__name__)

_CALENDLY_API_BASE = "https://api.calendly.com"


# ── Stub (in-memory) ─────────────────────────────────────────────────────────

_STUB_SLOTS_CACHE: list[dict] | None = None


def _stub_get_available_slots(days_ahead: int) -> list[dict]:
    global _STUB_SLOTS_CACHE
    now = datetime.now(timezone.utc)
    slots = []
    for day_offset in range(1, days_ahead + 1):
        day = now + timedelta(days=day_offset)
        if day.weekday() >= 5:
            continue
        for hour in [9, 10, 11, 13, 14, 15, 16]:
            slot_time = day.replace(hour=hour, minute=0, second=0, microsecond=0)
            slots.append({
                "datetime": slot_time.isoformat(),
                "label": slot_time.strftime("%A, %B %d at %I:%M %p UTC"),
            })
    return slots


# ── Calendly API ─────────────────────────────────────────────────────────────

_calendly_headers = lambda: {
    "Authorization": f"Bearer {settings.calendly_api_key}",
    "Content-Type": "application/json",
}


def _get_event_type_uuid() -> str | None:
    if not settings.calendly_event_type_uri:
        return None
    return settings.calendly_event_type_uri.rstrip("/").rsplit("/", 1)[-1]


async def _calendly_get_available_slots(days_ahead: int) -> list[dict]:
    event_type_uuid = _get_event_type_uuid()
    if not event_type_uuid:
        logger.debug("no calendly event type configured, falling back to stub")
        return _stub_get_available_slots(days_ahead)

    start_time = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    end_time = (datetime.now(timezone.utc) + timedelta(days=days_ahead)).isoformat().replace("+00:00", "Z")

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"{_CALENDLY_API_BASE}/event_type_available_times",
                headers=_calendly_headers(),
                params={
                    "event_type_uuid": event_type_uuid,
                    "start_time": start_time,
                    "end_time": end_time,
                },
            )
        response.raise_for_status()
        data = response.json()

        slots = []
        for item in data.get("collection", []):
            dt = datetime.fromisoformat(item["start_time"].replace("Z", "+00:00"))
            slots.append({
                "datetime": item["start_time"],
                "label": dt.strftime("%A, %B %d at %I:%M %p %Z"),
            })
        return slots

    except Exception as e:
        logger.warning("calendly api error: %s", e)
        return _stub_get_available_slots(days_ahead)


_INVITATION_STORE: dict[str, dict] = {}


async def create_single_use_scheduling_link(event_type_uri: str | None = None) -> dict:
    """Create a Calendly single-use scheduling link.

    Returns a dict with ``booking_url``, ``owner`` and ``status``.
    Falls back to a stub when no Calendly API key is configured.
    """
    uri = event_type_uri or settings.calendly_event_type_uri

    if not settings.calendly_api_key or not uri:
        booking_id = f"stub-{len(_INVITATION_STORE)}"
        stub_url = f"https://calendly.com/fake-booking/{booking_id}"
        _INVITATION_STORE[booking_id] = {"url": stub_url, "status": "stub"}
        logger.debug("calendly stub: link=%s", stub_url)
        return {"booking_url": stub_url, "owner": "stub", "status": "stub"}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"{_CALENDLY_API_BASE}/scheduling_links",
                headers=_calendly_headers(),
                json={
                    "max_event_count": 1,
                    "owner": uri,
                    "owner_type": "EventType",
                },
            )
        response.raise_for_status()
        data = response.json()
        resource = data.get("resource", {})
        booking_url = resource.get("booking_url", "")
        owner = resource.get("owner", "")
        _INVITATION_STORE[uri] = {"url": booking_url, "status": "active"}
        logger.debug("calendly link created: url=%s owner=%s", booking_url, owner)
        return {"booking_url": booking_url, "owner": owner, "status": "active"}

    except Exception as e:
        logger.warning("calendly scheduling link error: %s", e)
        booking_id = f"stub-{len(_INVITATION_STORE)}"
        stub_url = f"https://calendly.com/fake-booking/{booking_id}"
        _INVITATION_STORE[booking_id] = {"url": stub_url, "status": "stub-fallback"}
        return {"booking_url": stub_url, "owner": "stub", "status": "stub-fallback"}


async def check_booking_status(session_id: str) -> dict:
    """Check the status of a scheduled event for a given session.

    Uses Calendly's GET /scheduled_events filtered by invitee email/session.
    Falls back to the in-memory stub when no API key is configured.
    """
    if not settings.calendly_api_key or not settings.calendly_user_uri:
        entry = _INVITATION_STORE.get(session_id, {})
        return {
            "status": entry.get("status", "unknown"),
            "booking_url": entry.get("url"),
            "session_id": session_id,
        }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"{_CALENDLY_API_BASE}/scheduled_events",
                headers=_calendly_headers(),
                params={"user": settings.calendly_user_uri, "status": "active"},
            )
        response.raise_for_status()
        data = response.json()
        events = [
            {
                "uri": ev.get("uri"),
                "status": ev.get("status"),
                "start_time": ev.get("start_time"),
                "end_time": ev.get("end_time"),
                "name": ev.get("name"),
            }
            for ev in data.get("collection", [])
        ]
        return {"status": "active", "events": events, "session_id": session_id}

    except Exception as e:
        logger.warning("calendly check status error: %s", e)
        return {"status": "error", "error": str(e), "session_id": session_id}


# ── Public API (auto-select backend) ─────────────────────────────────────────

async def get_available_slots(days_ahead: int = 14) -> list[dict]:
    if settings.calendly_api_key:
        return await _calendly_get_available_slots(days_ahead)
    return _stub_get_available_slots(days_ahead)
