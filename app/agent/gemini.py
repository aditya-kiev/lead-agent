import asyncio
import logging
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

from app.config.settings import settings

logger = logging.getLogger(__name__)

# Per-turn Gemini call counter (reset per run_agent invocation)
gemini_call_counter: ContextVar[int] = ContextVar("gemini_call_counter", default=0)

# Shared concurrency limiter — caps in-flight calls to stay under the RPM ceiling
_gemini_semaphore: asyncio.Semaphore | None = None


def _get_semaphore() -> asyncio.Semaphore:
    global _gemini_semaphore
    if _gemini_semaphore is None:
        _gemini_semaphore = asyncio.Semaphore(int(settings.gemini_rpm_limit))
    return _gemini_semaphore


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


def _get_retry_delay(error: BaseException) -> float | None:
    """Try to extract a server-suggested retry delay from the exception.

    Priority:
    1. ``retry_after`` attribute (set by google-api-core for 429 responses)
    2. ``google.rpc.RetryInfo.retry_delay`` from protobuf details
    3. Fall back to *None* (caller uses exponential backoff instead)
    """
    for current in _iter_exception_chain(error):
        retry_after = getattr(current, "retry_after", None)
        if retry_after is not None:
            return float(retry_after)

        # Try to parse RetryInfo from protobuf details
        details = getattr(current, "details", None) or getattr(current, "error_details", None)
        if details:
            try:
                from google.protobuf import any_pb2
                from google.rpc import retry_info_pb2

                for detail in details:
                    if isinstance(detail, any_pb2.Any):
                        ri = retry_info_pb2.RetryInfo()
                        if detail.Unpack(ri):
                            nanos = ri.retry_delay.nanos or 0
                            seconds = ri.retry_delay.seconds or 0
                            if seconds > 0 or nanos > 0:
                                return seconds + nanos / 1_000_000_000
            except ImportError:
                pass

    return None


@dataclass
class RetryingGeminiModel:
    """Thin proxy that retries transient Gemini rate-limit failures.

    Concurrency is capped by a shared module-level ``asyncio.Semaphore``
    so that in-flight calls stay under the configured RPM ceiling
    (``settings.gemini_rpm_limit``).  Server-suggested retry delays
    (``Retry-After`` header, ``RetryInfo`` protobuf) are honoured when
    available; otherwise exponential backoff is used.
    """

    model: Any
    max_retries: int = 2
    initial_backoff_seconds: float = 0.5

    def __getattr__(self, name: str) -> Any:
        return getattr(self.model, name)

    async def ainvoke(self, *args: Any, **kwargs: Any) -> Any:
        counter = gemini_call_counter
        counter.set(counter.get() + 1)

        sem = _get_semaphore()

        async with sem:
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
                            "The AI service is temporarily rate limited. "
                            "Please try again in a minute."
                        ) from exc

                    # Use server-suggested delay if available, else exponential
                    suggested = _get_retry_delay(exc)
                    sleep_for = suggested if suggested is not None else delay
                    await asyncio.sleep(sleep_for)
                    delay *= 2
