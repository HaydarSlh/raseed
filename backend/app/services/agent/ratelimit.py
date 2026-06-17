"""Per-user write rate limiter: Redis fixed-window counter, 10 writes/min (FR-020)."""

from __future__ import annotations

import uuid

from app.core.exceptions import RaseedError
from app.infra.redis import get_redis


class RateLimitExceeded(RaseedError):
    pass


async def check_write_rate(user_id: uuid.UUID, *, limit: int = 10, window_seconds: int = 60) -> None:
    """Increment the per-user write counter; raise RateLimitExceeded on the (limit+1)th call."""
    redis = get_redis()
    key = f"raseed:write_rate:{user_id}"
    pipe = redis.pipeline()
    pipe.incr(key)
    pipe.expire(key, window_seconds, nx=True)
    results = await pipe.execute()
    count: int = results[0]
    if count > limit:
        raise RateLimitExceeded(
            f"Write rate limit exceeded: {limit} writes per {window_seconds}s. Please wait before trying again."
        )
