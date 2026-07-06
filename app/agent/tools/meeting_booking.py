from datetime import datetime


_BOOKED_MEETINGS: dict[str, dict] = {}


def book_meeting(session_id: str, proposed_time: str, timezone: str = "UTC") -> dict:
    meeting_id = f"mtg-{session_id}-{int(datetime.utcnow().timestamp())}"
    meeting_data = {
        "meeting_id": meeting_id,
        "session_id": session_id,
        "proposed_time": proposed_time,
        "timezone": timezone,
        "status": "confirmed",
        "created_at": datetime.utcnow().isoformat(),
    }
    _BOOKED_MEETINGS[session_id] = meeting_data
    return meeting_data


def get_booking(session_id: str) -> dict | None:
    return _BOOKED_MEETINGS.get(session_id)


def cancel_booking(session_id: str) -> bool:
    return _BOOKED_MEETINGS.pop(session_id, None) is not None
