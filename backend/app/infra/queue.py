"""RQ queue wiring for the light worker: recompute analytics after a write,
and the privileged population-stats job. Enqueue helpers live here so the
service layer never imports rq directly (constitution Art. I layering)."""

from __future__ import annotations

import uuid

import redis
from rq import Queue

from app.core.config import get_settings

# Two named queues on the same Redis pool:
#   default — per-user recompute (invalidate-on-write, constitution Art. V)
#   stats   — cross-user population_stats job (BYPASSRLS role, constitution Art. II)
_DEFAULT_QUEUE_NAME = "default"
_STATS_QUEUE_NAME = "stats"

_redis_conn: redis.Redis | None = None  # type: ignore[type-arg]


def _get_redis() -> redis.Redis:  # type: ignore[type-arg]
    global _redis_conn
    if _redis_conn is None:
        settings = get_settings()
        _redis_conn = redis.from_url(settings.redis_url)
    return _redis_conn


def get_recompute_queue() -> Queue:
    return Queue(_DEFAULT_QUEUE_NAME, connection=_get_redis())


def get_stats_queue() -> Queue:
    return Queue(_STATS_QUEUE_NAME, connection=_get_redis())


def enqueue_recompute(user_id: uuid.UUID) -> None:
    """Enqueue a per-user analytics recompute (forecast + anomaly + recurring detection).

    Called immediately after any successful transaction write so derived data is
    never stale longer than the worker latency (constitution Art. V).
    """
    queue = get_recompute_queue()
    queue.enqueue(
        "workers.recompute.run",
        kwargs={"user_id": str(user_id)},
        job_timeout=300,
    )


def enqueue_population_stats() -> None:
    """Enqueue the privileged cross-user stats refresh.

    Only called from the scheduler (light worker cron) or manually by ops,
    never from a user-facing request path (constitution Art. II).
    """
    queue = get_stats_queue()
    queue.enqueue(
        "workers.stats.run",
        job_timeout=600,
    )
