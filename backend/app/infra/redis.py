"""Async Redis client singleton for session memory and rate limiting (Phase 4, constitution Art. IV/V)."""

from __future__ import annotations

import redis.asyncio as aioredis

from app.core.config import get_settings

_async_client: aioredis.Redis | None = None


def init_async_redis() -> aioredis.Redis:
    global _async_client
    settings = get_settings()
    _async_client = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _async_client


def get_redis() -> aioredis.Redis:
    if _async_client is None:
        return init_async_redis()
    return _async_client


async def close_redis() -> None:
    global _async_client
    if _async_client is not None:
        await _async_client.aclose()
        _async_client = None
