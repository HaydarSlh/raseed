"""FastAPI application factory: wires lifespan singletons, middleware, exception handlers, and routers (constitution Art. I)."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import analytics as analytics_router
from app.api import auth as auth_router
from app.api import health
from app.api import ingestion as ingestion_router
from app.api.chat import router as chat_router
from app.api.erasure import router as erasure_router
from app.api.goals import router as goals_router
from app.api.ops import router as ops_router
from app.api.review import router as review_router
from app.api.settings import router as settings_router
from app.core.exceptions import RaseedError
from app.core.lifespan import lifespan
from app.core.request_context import RequestIdMiddleware


def create_app() -> FastAPI:
    """Build the FastAPI app with all middleware, exception handlers, and routers."""
    app = FastAPI(title="Raseed", version="0.1.0", lifespan=lifespan)

    # Middleware (outermost first — request-id before CORS)
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Domain-exception → structured HTTP — users never see a stack trace (FR-012)
    @app.exception_handler(RaseedError)
    async def raseed_error_handler(request: Request, exc: RaseedError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message},
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={"detail": "An unexpected error occurred."},
        )

    # Routers
    app.include_router(health.router)
    app.include_router(auth_router.router)
    app.include_router(ingestion_router.router)
    app.include_router(analytics_router.router)
    app.include_router(chat_router)
    app.include_router(goals_router)
    app.include_router(review_router)
    app.include_router(settings_router)
    app.include_router(ops_router)
    app.include_router(erasure_router)

    return app


app = create_app()
