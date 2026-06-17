"""Redis-backed short-term conversation context: 30-min sliding TTL per session (FR-017, Art. IV)."""

from __future__ import annotations

import json

from app.infra.redis import get_redis


async def load_context(session_id: str, *, ttl: int = 1800) -> list[dict]:
    """Load conversation turns for a session; refresh the TTL on access."""
    redis = get_redis()
    key = f"raseed:session:{session_id}"
    raw = await redis.get(key)
    if raw:
        await redis.expire(key, ttl)
        return json.loads(raw)
    return []


async def append_turn(session_id: str, role: str, content: str, *, ttl: int = 1800) -> None:
    """Append a turn to the session and reset the sliding TTL."""
    redis = get_redis()
    key = f"raseed:session:{session_id}"
    raw = await redis.get(key)
    turns: list[dict] = json.loads(raw) if raw else []
    turns.append({"role": role, "content": content})
    # Keep only the last 20 turns to bound context size
    turns = turns[-20:]
    await redis.setex(key, ttl, json.dumps(turns))


async def clear_session(session_id: str) -> None:
    """Explicitly remove a session (e.g., on logout)."""
    redis = get_redis()
    await redis.delete(f"raseed:session:{session_id}")
