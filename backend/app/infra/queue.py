"""RQ queue wiring for the light worker: recompute analytics after a write,
the privileged population-stats job, and the training queue for ML lifecycle jobs.

Enqueue helpers live here so the service layer never imports rq directly
(constitution Art. I layering)."""

from __future__ import annotations

import uuid

import redis
from rq import Queue

from app.core.config import get_settings

# Named queues on the same Redis pool:
#   default  — per-user recompute (invalidate-on-write, constitution Art. V)
#   stats    — cross-user population_stats job (BYPASSRLS role, constitution Art. II)
#   training — ML retrain jobs (trainer container, heavy, off default profile)
_DEFAULT_QUEUE_NAME = "default"
_STATS_QUEUE_NAME = "stats"
_TRAINING_QUEUE_NAME = "training"

_redis_conn: redis.Redis | None = None


def _get_redis() -> redis.Redis:
    global _redis_conn
    if _redis_conn is None:
        settings = get_settings()
        _redis_conn = redis.from_url(settings.redis_url)
    return _redis_conn


def get_recompute_queue() -> Queue:
    return Queue(_DEFAULT_QUEUE_NAME, connection=_get_redis())


def get_stats_queue() -> Queue:
    return Queue(_STATS_QUEUE_NAME, connection=_get_redis())


def get_training_queue() -> Queue:
    return Queue(_TRAINING_QUEUE_NAME, connection=_get_redis())


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


def enqueue_retrain(
    retrain_run_id: uuid.UUID,
    idempotency_key: str,
    trigger_reason: str,
    *,
    demo_mode: bool = False,
) -> None:
    """Enqueue a training job on the RQ `training` queue.

    The trainer worker refuses a duplicate idempotency_key (checked before
    enqueue in the trigger service; the trainer also guards it).
    Heavy trainer container consumes the `training` queue only (off-default profile).
    """
    queue = get_training_queue()
    queue.enqueue(
        "train.run",
        kwargs={
            "retrain_run_id": str(retrain_run_id),
            "idempotency_key": idempotency_key,
            "trigger_reason": trigger_reason,
            "demo_mode": demo_mode,
        },
        job_timeout=3600,
    )
