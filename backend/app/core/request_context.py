"""Request-id middleware: assigns a UUID per request and binds it into structlog contextvars so every log line carries the same id (constitution Art. V, FR-011)."""

from __future__ import annotations

import uuid
from contextvars import ContextVar
from typing import Any

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

REQUEST_ID_CTX: ContextVar[str] = ContextVar("request_id", default="")


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Any) -> Response:
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        REQUEST_ID_CTX.set(request_id)
        structlog.contextvars.bind_contextvars(request_id=request_id)
        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.clear_contextvars()
        response.headers["x-request-id"] = request_id
        return response
