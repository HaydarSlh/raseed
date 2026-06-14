"""Tracing span context manager and tenacity retry helper for external calls; 4xx responses are never retried (constitution Art. V)."""

from __future__ import annotations

import time
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

import structlog
import tenacity

log = structlog.get_logger(__name__)


@contextmanager
def span(name: str, **kv: Any) -> Generator[None, None, None]:
    """Log the start + end of an external call with elapsed ms and any extra fields."""
    t0 = time.monotonic()
    log.debug(f"{name}.start", **kv)
    try:
        yield
    except Exception as exc:
        elapsed_ms = round((time.monotonic() - t0) * 1000, 1)
        log.warning(f"{name}.error", elapsed_ms=elapsed_ms, error=str(exc), **kv)
        raise
    else:
        elapsed_ms = round((time.monotonic() - t0) * 1000, 1)
        log.debug(f"{name}.ok", elapsed_ms=elapsed_ms, **kv)


def is_retryable(exc: BaseException) -> bool:
    """4xx HTTP-like errors are client errors — do not retry them."""
    status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
    if status is not None and 400 <= int(status) < 500:
        return False
    return True


def with_retry(
    *,
    max_attempts: int = 3,
    wait_min: float = 1.0,
    wait_max: float = 8.0,
    timeout: float = 30.0,
) -> tenacity.AsyncRetrying:
    """Return a tenacity AsyncRetrying configured with bounded exponential backoff.

    4xx errors propagate immediately (client error — retrying wastes quota). All
    other exceptions retry up to `max_attempts` times within `timeout` seconds.
    """
    return tenacity.AsyncRetrying(
        retry=tenacity.retry_if_exception(is_retryable),
        stop=(
            tenacity.stop_after_attempt(max_attempts)
            | tenacity.stop_after_delay(timeout)
        ),
        wait=tenacity.wait_exponential(min=wait_min, max=wait_max),
        reraise=True,
    )
