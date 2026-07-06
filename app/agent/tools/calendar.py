from datetime import datetime, timedelta


_AVAILABLE_SLOTS_CACHE: list[dict] | None = None


def get_available_slots(days_ahead: int = 14) -> list[dict]:
    global _AVAILABLE_SLOTS_CACHE
    now = datetime.utcnow()
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


def invalidate_cache():
    global _AVAILABLE_SLOTS_CACHE
    _AVAILABLE_SLOTS_CACHE = None
