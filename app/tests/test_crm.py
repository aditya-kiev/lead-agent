from unittest.mock import AsyncMock, MagicMock, patch

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _clear_crm_leads():
    from app.agent.tools.crm import _CRM_LEADS
    _CRM_LEADS.clear()
    yield


@pytest.mark.asyncio
async def test_update_crm_stores_locally():
    """update_crm must always write to _CRM_LEADS regardless of webhook config."""
    from app.agent.tools.crm import update_crm, get_crm_lead

    with patch("app.config.settings.settings.crm_webhook_url", None):
        result = await asyncio.to_thread(update_crm, "test-session", {"lead_name": "Alice", "budget": 50000})
        assert result["lead_name"] == "Alice"
        assert result["session_id"] == "test-session"

    loaded = get_crm_lead("test-session")
    assert loaded is not None
    assert loaded["lead_name"] == "Alice"


@pytest.mark.asyncio
async def test_webhook_not_fired_when_url_unset():
    """When CRM_WEBHOOK_URL is unset, update_crm must not fire any HTTP calls."""
    from app.agent.tools.crm import update_crm

    with patch("app.config.settings.settings.crm_webhook_url", None):
        with patch("app.agent.tools.crm._fire_webhook") as mock_fire:
            await asyncio.to_thread(update_crm, "test-session", {"lead_name": "Alice"})
            mock_fire.assert_not_called()


@pytest.mark.asyncio
async def test_webhook_retries_then_gives_up():
    """_fire_webhook must retry on failures up to 3 attempts, then give up."""
    from app.agent.tools.crm import _fire_webhook

    with patch("app.config.settings.settings.crm_webhook_url", "https://example.com/webhook"):
        mock_client = AsyncMock()
        mock_post = MagicMock()
        mock_post.is_success = False
        mock_post.status_code = 500
        mock_client.post = AsyncMock(return_value=mock_post)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                await _fire_webhook({"session_id": "test"}, max_retries=3)

            assert mock_client.post.call_count == 3, (
                f"Expected 3 retries, got {mock_client.post.call_count}"
            )


@pytest.mark.asyncio
async def test_webhook_payload_shape():
    """The webhook payload must contain the expected lead fields."""
    from app.agent.tools.crm import update_crm, _CRM_LEADS

    _CRM_LEADS.clear()
    with patch("app.config.settings.settings.crm_webhook_url", "https://example.com/webhook"):
        with patch("app.agent.tools.crm._fire_webhook"):
            # Call synchronously; the event loop is running so ensure_future works
            result = update_crm("shape-test", {
                "lead_name": "Bob",
                "budget": 100000,
                "lead_status": "hot",
                "qualification_score": 0.9,
            })

    assert result["session_id"] == "shape-test"
    assert result["lead_name"] == "Bob"
    assert result["budget"] == 100000
    assert "updated_at" in result
