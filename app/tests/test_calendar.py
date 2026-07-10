from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.tools.calendar import (
    get_available_slots,
    create_single_use_scheduling_link,
    check_booking_status,
)
from app.config.settings import settings


async def test_stub_get_available_slots():
    """Without Calendly credentials, returns generated weekday slots."""
    with patch.object(settings, "calendly_api_key", ""):
        slots = await get_available_slots(days_ahead=3)

    assert len(slots) > 0
    for s in slots:
        assert "datetime" in s
        assert "label" in s


async def test_stub_create_scheduling_link():
    """Without Calendly credentials, returns a stub link."""
    with patch.object(settings, "calendly_api_key", ""), \
         patch.object(settings, "calendly_event_type_uri", ""):
        result = await create_single_use_scheduling_link()

    assert result["status"] == "stub"
    assert "calendly.com/fake-booking" in result["booking_url"]


async def test_stub_check_booking_status():
    """Without Calendly credentials, returns status from in-memory store."""
    with patch.object(settings, "calendly_api_key", ""), \
         patch.object(settings, "calendly_user_uri", ""):
        result = await check_booking_status("unknown-id")

    assert result["status"] == "unknown"
    assert result["session_id"] == "unknown-id"


def _mock_async_client(json_data, status_code=200):
    """Helper to build a mock ``httpx.AsyncClient`` context manager."""
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.json.return_value = json_data
    mock_response.raise_for_status.return_value = None

    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.post = AsyncMock(return_value=mock_response)

    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_client)
    mock_cm.__aexit__ = AsyncMock(return_value=None)

    return patch("app.agent.tools.calendar.httpx.AsyncClient", return_value=mock_cm)


async def test_calendly_get_available_slots():
    """With credentials, fetches slots from Calendly API."""
    with patch.object(settings, "calendly_api_key", "test-key"), \
         patch.object(settings, "calendly_event_type_uri",
                      "https://api.calendly.com/event_types/UUID123"), \
         _mock_async_client({
             "collection": [
                 {
                     "start_time": "2026-07-15T09:00:00Z",
                     "end_time": "2026-07-15T09:30:00Z",
                     "status": "available",
                 },
             ]
         }):

        slots = await get_available_slots(days_ahead=3)

    assert len(slots) == 1
    assert slots[0]["datetime"] == "2026-07-15T09:00:00Z"


async def test_calendly_create_scheduling_link():
    """With credentials, creates a scheduling link via Calendly API."""
    with patch.object(settings, "calendly_api_key", "test-key"), \
         patch.object(settings, "calendly_event_type_uri",
                      "https://api.calendly.com/event_types/UUID123"), \
         _mock_async_client({
             "resource": {
                 "booking_url": "https://calendly.com/me/test-link",
                 "owner": "https://api.calendly.com/event_types/UUID123",
                 "owner_type": "EventType",
             },
         }):

        result = await create_single_use_scheduling_link()

    assert result["status"] == "active"
    assert result["booking_url"] == "https://calendly.com/me/test-link"


async def test_calendly_get_available_slots_fallback_on_error():
    """On API error, falls back to stub slots."""
    mock_client = MagicMock()
    mock_client.get = AsyncMock(side_effect=Exception("API down"))

    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_client)
    mock_cm.__aexit__ = AsyncMock(return_value=None)

    with patch.object(settings, "calendly_api_key", "test-key"), \
         patch.object(settings, "calendly_event_type_uri",
                      "https://api.calendly.com/event_types/UUID123"), \
         patch("app.agent.tools.calendar.httpx.AsyncClient", return_value=mock_cm):

        slots = await get_available_slots(days_ahead=5)

    assert len(slots) > 0
    assert "datetime" in slots[0]
    assert "label" in slots[0]
