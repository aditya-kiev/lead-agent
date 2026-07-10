import asyncio
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


class GeminiRateLimitError(Exception):
    """Raised when Gemini is rate limited after retrying."""


def _iter_exception_chain(error: BaseException):
    current: BaseException | None = error
    seen: set[int] = set()

    while current is not None and id(current) not in seen:
        seen.add(id(current))
        yield current
        current = current.__cause__ or current.__context__


def _is_rate_limited_gemini_error(error: BaseException) -> bool:
    for current in _iter_exception_chain(error):
        code = getattr(current, "code", None)
        status_code = getattr(current, "status_code", None)
        status = getattr(current, "status", None)
        message = str(current).upper()

        if code == 429 or status_code == 429:
            return True
        if status == "RESOURCE_EXHAUSTED":
            return True
        if "RESOURCE_EXHAUSTED" in message and "429" in message:
            return True

    return False


@dataclass
class RetryingGeminiModel:
    """Thin proxy that retries transient Gemini rate-limit failures."""

    model: Any
    max_retries: int = 2
    initial_backoff_seconds: float = 0.5

    def __getattr__(self, name: str) -> Any:
        return getattr(self.model, name)

    async def ainvoke(self, *args: Any, **kwargs: Any) -> Any:
        delay = self.initial_backoff_seconds
        attempts = self.max_retries + 1

        for attempt in range(1, attempts + 1):
            try:
                return await self.model.ainvoke(*args, **kwargs)
            except Exception as exc:
                if not _is_rate_limited_gemini_error(exc):
                    raise

                logger.exception(
                    "Gemini rate limit encountered (attempt %s/%s)",
                    attempt,
                    attempts,
                )

                if attempt >= attempts:
                    raise GeminiRateLimitError(
                        "The AI service is temporarily rate limited. Please try again in a minute."
                    ) from exc

                await asyncio.sleep(delay)
                delay *= 2
