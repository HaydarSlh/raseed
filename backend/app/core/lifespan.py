"""App lifespan: constructs and tears down expensive shared singletons — engine, session factory, Vault secrets, LLM adapter (constitution Art. I)."""

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
    """Build shared singletons on startup; release on shutdown."""
    settings = get_settings()
    configure_logging(settings.log_level)
    log = get_logger("lifespan")
    log.info("startup", app_env=settings.app_env)

    from app.infra.db import dispose_engine, init_engine
    from app.infra.embeddings import build_embedder, init_embedder
    from app.infra.llm import build_llm, init_llm
    from app.infra.redis import close_redis, init_async_redis
    from app.infra.vault import load_secrets_into_settings

    # 1. Vault — resolve secrets; fail-fast in non-local envs (Art. V, FR-010)
    vault_secrets = load_secrets_into_settings()
    if "jwt_secret" in vault_secrets:
        # Override the in-process Settings value with the Vault-sourced secret
        settings.__dict__["jwt_secret"] = vault_secrets["jwt_secret"]

    # 2. DB engine + session factory (pool reset hook wired inside)
    init_engine(settings.database_url)
    log.info("db.engine.ready")

    # 3. LLM adapter — FakeLLM when no keys, real adapter otherwise
    llm = build_llm(
        gemini_api_key=settings.gemini_api_key,
        grok_api_key=settings.grok_api_key,
        use_fake=settings.use_fake_llm,
    )
    init_llm(llm)
    log.info("llm.adapter.ready", provider=type(llm).__name__)

    # 4. Async Redis client for session memory + rate limiting
    init_async_redis()
    log.info("redis.async_client.ready")

    # 5. Embedder — FakeEmbedder when no Gemini key or use_fake_llm=True
    embedder = build_embedder(
        gemini_api_key=settings.gemini_api_key,
        use_fake=settings.use_fake_llm,
        dim=settings.embedding_dim,
        model=settings.embedding_model,
    )
    init_embedder(embedder)
    log.info("embedder.ready", provider=type(embedder).__name__)

    try:
        yield
    finally:
        log.info("shutdown")
        await dispose_engine()
        await close_redis()
