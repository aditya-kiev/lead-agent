from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health_endpoint(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == "1.0.0"


@pytest.mark.asyncio
async def test_webhook_message_requires_api_key(client):
    """Without API key header, webhook/message should return 401 when API key is set."""
    with patch("app.config.settings.settings.api_key", "test-secret-key"):
        payload = {"session_id": "test-session", "message": "Hello"}
        response = await client.post("/webhook/message", json=payload)
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_webhook_message_with_valid_api_key(client):
    """With valid API key header, webhook/message should accept the request."""
    with patch("app.config.settings.settings.api_key", "test-secret-key"):
        with patch("app.api.webhook.run_agent", new_callable=AsyncMock) as mock_agent:
            mock_agent.return_value = {
                "conversation_history": [],
                "lead_status": None,
                "booking_confirmed": False,
                "meeting_time": None,
                "human_escalated": False,
                "next_action": None,
            }
            payload = {"session_id": "test-session", "message": "Hello"}
            response = await client.post(
                "/webhook/message",
                json=payload,
                headers={"X-API-Key": "test-secret-key"},
            )
            assert response.status_code == 200


@pytest.mark.asyncio
async def test_webhook_message_skips_auth_when_no_key_configured(client):
    """When settings.api_key is empty (local dev), auth should be skipped."""
    with patch("app.config.settings.settings.api_key", ""):
        with patch("app.api.webhook.run_agent", new_callable=AsyncMock) as mock_agent:
            mock_agent.return_value = {
                "conversation_history": [],
                "lead_status": None,
                "booking_confirmed": False,
                "meeting_time": None,
                "human_escalated": False,
                "next_action": None,
            }
            payload = {"session_id": "test-session", "message": "Hello"}
            response = await client.post(
                "/webhook/message", json=payload
            )
            assert response.status_code == 200


@pytest.mark.asyncio
async def test_debug_state_not_mounted_in_production(client):
    """Debug router should not be mounted when settings.debug is False."""
    with patch("app.config.settings.settings.debug", False):
        response = await client.get("/debug/state/test-session")
        assert response.status_code == 404
