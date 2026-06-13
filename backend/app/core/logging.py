"""structlog JSON logging with request-id support, shared across API, queue, and workers (constitution Art. V)."""

from __future__ import annotations

import logging

import structlog


def configure_logging(level: str = "INFO") -> None:
    """Configure structlog to emit JSON with ISO timestamps and a request-id slot.
    Spans carrying token/cost fields for LLM/tool/retrieval calls are added in the
    phases that introduce those calls."""
    logging.basicConfig(format="%(message)s", level=getattr(logging, level.upper(), logging.INFO))
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger."""
    return structlog.get_logger(name)
