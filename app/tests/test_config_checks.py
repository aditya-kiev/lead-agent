from unittest.mock import patch

import pytest

from app.config.checks import check_production_api_key


@pytest.mark.asyncio
async def test_production_without_api_key_raises():
    """check_production_api_key must raise RuntimeError when ENVIRONMENT=production and API_KEY is empty."""
    with patch("app.config.settings.settings.environment", "production"):
        with patch("app.config.settings.settings.api_key", ""):
            with pytest.raises(RuntimeError):
                check_production_api_key()


@pytest.mark.asyncio
async def test_production_with_api_key_passes():
    """check_production_api_key must not raise when ENVIRONMENT=production and API_KEY is set."""
    with patch("app.config.settings.settings.environment", "production"):
        with patch("app.config.settings.settings.api_key", "some-secret"):
            check_production_api_key()


@pytest.mark.asyncio
async def test_development_without_api_key_passes():
    """check_production_api_key must be a no-op in development even without API_KEY."""
    with patch("app.config.settings.settings.environment", "development"):
        with patch("app.config.settings.settings.api_key", ""):
            check_production_api_key()
