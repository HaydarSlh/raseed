"""Liveness router: exposes GET /healthz so the backend reports healthy on an empty boot (Phase 0)."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    """Liveness probe used by compose healthchecks. No business logic."""
    return {"status": "ok"}
