"""FastAPI application factory: wires lifespan singletons and routers; boots empty with only /healthz in Phase 0 (constitution Art. I)."""

from __future__ import annotations

from fastapi import FastAPI

from app.api import health
from app.core.lifespan import lifespan


def create_app() -> FastAPI:
    """Build the FastAPI app. Business routers are added in later phases; Phase 0
    exposes only the liveness probe so the service boots healthy and empty."""
    app = FastAPI(title="Raseed", version="0.0.0", lifespan=lifespan)
    app.include_router(health.router)
    return app


app = create_app()
