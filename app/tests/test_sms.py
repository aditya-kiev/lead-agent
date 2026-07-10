from unittest.mock import MagicMock, patch

import pytest

from app.agent.tools.sms import send_sms, get_stub_sms_log
from app.config.settings import settings


async def test_sms_stub_fallback_without_credentials():
    """Without Twilio credentials, send_sms logs to an in-memory stub."""
    with patch.object(settings, "twilio_account_sid", ""):
        result = await send_sms("+15551234567", "Hello from the stub!")

    assert result["sid"].startswith("stub-")
    assert result["status"] == "sent"
    assert result["to"] == "+15551234567"
    assert "stub" in result["body"]

    log = get_stub_sms_log()
    assert any(e["sid"] == result["sid"] for e in log)


async def test_sms_calls_twilio_when_configured():
    """With Twilio credentials, send_sms calls the Twilio API via thread."""
    mock_message = MagicMock()
    mock_message.sid = "SM123"
    mock_message.status = "queued"

    mock_client = MagicMock()
    mock_client.messages.create = MagicMock(return_value=mock_message)

    with patch.object(settings, "twilio_account_sid", "test-sid"), \
         patch.object(settings, "twilio_auth_token", "test-token"), \
         patch.object(settings, "twilio_from_number", "+15551234567"), \
         patch("twilio.rest.Client", return_value=mock_client):

        result = await send_sms("+15559876543", "Your meeting is confirmed!")

    assert result["sid"] == "SM123"
    assert result["status"] == "queued"

    mock_client.messages.create.assert_called_once_with(
        body="Your meeting is confirmed!",
        from_="+15551234567",
        to="+15559876543",
    )
