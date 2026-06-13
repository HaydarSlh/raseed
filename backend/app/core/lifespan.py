"""App lifespan: constructs and tears down expensive shared singletons (DB engine, Redis, MinIO, Vault, LLM adapter, model-server client) per constitution Art. I."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger

if TYPE_CHECKING:
    from fastapi import FastAPI


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Build shared singletons on startup, release them on shutdown.

    Phase 0 wires the seams without opening real connections — the empty stack
    boots without any business dependency. Later phases attach the actual clients
    to `app.state` here (lifespan singletons, never per-request construction)."""
    settings = get_settings()
    configure_logging(settings.log_level)
    log = get_logger("lifespan")
    log.info("startup", app_env=settings.app_env)

    # Later phases: app.state.db = create_async_engine(...), redis, minio, vault,
    # llm_adapter, modelserver_client — all constructed once, here.

    try:
        yield
    finally:
        log.info("shutdown")
        # Later phases: dispose engine, close redis/minio/vault clients.
