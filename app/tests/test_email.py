from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _clear_email_log():
    from app.agent.tools.email import _EMAIL_LOG
    _EMAIL_LOG.clear()
    yield


def test_send_email_keeps_log():
    """send_email must always append to _EMAIL_LOG regardless of settings."""
    from app.agent.tools.email import send_email, get_email_log

    with patch("app.config.settings.settings.resend_api_key", ""):
        result = send_email("test@example.com", "Test", "Body")
        assert result["status"] == "sent"
    log = get_email_log()
    assert len(log) == 1
    assert log[0]["to"] == "test@example.com"
    assert log[0]["subject"] == "Test"


def test_send_email_makes_real_api_call_when_configured():
    """When RESEND_API_KEY is set, send_email must call the Resend API."""
    from app.agent.tools.email import send_email, get_email_log

    with patch("app.config.settings.settings.resend_api_key", "re_test"):
        with patch("app.config.settings.settings.resend_from_email", "onboarding@resend.dev"):
            with patch("httpx.post") as mock_post:
                mock_post.return_value.is_success = True
                mock_post.return_value.status_code = 200

                result = send_email("boss@example.com", "Hot Lead", "Lead details...")

                assert result["status"] == "sent"
                mock_post.assert_called_once_with(
                    "https://api.resend.com/emails",
                    headers=ANY,
                    json={
                        "from": "onboarding@resend.dev",
                        "to": ["boss@example.com"],
                        "subject": "Hot Lead",
                        "text": "Lead details...",
                    },
                    timeout=15.0,
                )

    log = get_email_log()
    assert len(log) == 1
    assert log[0]["to"] == "boss@example.com"


def test_send_email_does_not_crash_on_failure():
    """A failed Resend call must NOT raise — it logs and returns with status='failed'."""
    from app.agent.tools.email import send_email, get_email_log

    with patch("app.config.settings.settings.resend_api_key", "re_test"):
        with patch("httpx.post", side_effect=Exception("Network error")):
            result = send_email("boss@example.com", "Hot Lead", "Body")
            assert result["status"] == "failed"

    log = get_email_log()
    assert len(log) == 1


@pytest.mark.asyncio
async def test_hot_alert_dedupe():
    """A session that sends a hot alert once must NOT send a second one
    on a subsequent hot-status turn."""
    from datetime import datetime
    from app.database.models import LeadConversation

    mock_lead = MagicMock(spec=LeadConversation)
    mock_lead.hot_alert_sent_at = datetime.utcnow()  # Already sent
    mock_lead.lead_name = "Alice"
    mock_lead.budget = 500000.0
    mock_lead.qualification_score = 0.85
    mock_lead.timeline = "3 months"
    mock_lead.meeting_time = None

    from app.api.webhook import _maybe_send_hot_alert

    with patch("app.api.webhook.send_email") as mock_send:
        with patch("app.api.webhook.get_conversation", new_callable=AsyncMock, return_value=mock_lead):
            await _maybe_send_hot_alert("test-session", {"lead_status": "hot"})
            mock_send.assert_not_called()
