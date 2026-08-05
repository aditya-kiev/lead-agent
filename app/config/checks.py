import logging

from app.config.settings import settings

logger = logging.getLogger(__name__)


def check_production_api_key() -> None:
    """Raise RuntimeError if ENVIRONMENT=production but API_KEY is unset."""
    if settings.environment == "production" and not settings.api_key:
        raise RuntimeError(
            "API_KEY must be set when ENVIRONMENT=production. "
            'Generate one with: python -c "import secrets; print(secrets.token_urlsafe(32))"'
        )


check_production_api_key()