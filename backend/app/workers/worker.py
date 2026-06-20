"""Light-worker bootstrap: connects to Redis and consumes default and stats queues.

Entrypoint for the `worker` compose service (constitution Art. V).
The `training` queue is consumed SOLELY by the heavy trainer container under the
`training` compose profile — the light worker never listens on it, so it cannot
race the trainer and fail jobs it cannot execute (Art. III).
Daily drift monitor runs via RQ-Scheduler.
"""

from __future__ import annotations

from redis import Redis
from rq import Queue, Worker

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger


async def run_drift_check() -> None:
    """On-demand or scheduled drift evaluation — enqueued via RQ."""
    from app.infra.db import get_session_factory
    from app.workers.drift import run_drift_monitor

    factory = get_session_factory()
    async with factory() as session:
        await run_drift_monitor(session, source="scheduled")


async def run_batch_relabel(user_id: str) -> None:
    """Batch-relabel flagged rows for a user who switched to auto_relabel mode."""
    import uuid as _uuid

    from sqlalchemy import select

    from app.domain.transaction import Transaction
    from app.infra.db import get_session_factory
    from app.services.review.relabel import RelabelService

    factory = get_session_factory()
    async with factory() as session:
        uid = _uuid.UUID(user_id)
        result = await session.execute(
            select(Transaction)
            .where(Transaction.user_id == uid)
            .where(Transaction.needs_review == True)  # noqa: E712
        )
        txns = list(result.scalars().all())
        svc = RelabelService(session, uid)
        batch = [
            (t.id, t.normalized_description or "", t.category or "other")
            for t in txns
            if t.normalized_description
        ]
        if batch:
            await svc.relabel_batch(batch)
            await session.commit()


def main() -> None:
    """Boot the light worker listening on default and stats queues."""
    settings = get_settings()
    configure_logging(settings.log_level)
    log = get_logger("worker")
    log.info("worker_boot", redis_url=settings.redis_url)

    connection = Redis.from_url(settings.redis_url)
    queues = [
        Queue("default", connection=connection),
        Queue("stats", connection=connection),
    ]
    worker = Worker(queues, connection=connection)
    worker.work(with_scheduler=True)  # enable scheduler for daily drift


if __name__ == "__main__":
    main()
