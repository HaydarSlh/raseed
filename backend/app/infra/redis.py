"""Redis adapter for sessions and RQ queues; short-term agent memory lands here later (constitution Art. IV). Stub in Phase 0."""

from __future__ import annotations

# Phase 1+ attaches an async Redis client (settings.redis_url) as a lifespan
# singleton and the RQ queue handles ("training" and the light queue).
