"""DELETE /users/me/erasure — right-to-erasure endpoint (Phase 6, FR-008/FR-009)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_active_user
from app.infra.db import get_async_session
from app.domain.user import User
from app.schemas.erasure import ErasureResponse
from app.services.erasure import ErasureService

router = APIRouter(prefix="/users/me", tags=["erasure"])


@router.delete("/erasure", status_code=202, response_model=ErasureResponse)
async def request_erasure(
    user: User = Depends(current_active_user),  # noqa: B008
    session: AsyncSession = Depends(get_async_session),  # noqa: B008
) -> ErasureResponse:
    """Permanently delete all data owned by the authenticated user.

    Purges all Postgres rows, pgvector memory, and Redis session keys.
    Writes an operator-only erasure_audit record. This action is irreversible.
    """
    service = ErasureService(session)
    return await service.erase_user(user.id)
