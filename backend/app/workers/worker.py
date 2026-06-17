"""Light-worker bootstrap: connects to Redis and consumes the default RQ queue. Entrypoint for the `worker` compose service (constitution Art. V). Stub in Phase 0."""

from __future__ import annotations

from redis import Redis
from rq import Queue, Worker

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger


def main() -> None:
    """Boot the light worker: connect to Redis and block listening on the default
    queue. Phase 0 registers no jobs, so the worker simply stays alive and idle;
    Phase 3+ enqueues the stats, drift, and Slack-webhook jobs."""
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
    worker.work(with_scheduler=False)


if __name__ == "__main__":
    main()
