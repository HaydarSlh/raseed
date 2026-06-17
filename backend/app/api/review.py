"""Review queue API: GET /review/queue, POST /review/confirm — user-scoped via RLS session (constitution Art. II/III, FR-001/003)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_active_user
from app.db.session import get_rls_session
from app.domain.user import User
from app.schemas.review import ConfirmRequest, ConfirmResponse, ReviewQueueResponse
from app.services.review.queue import ReviewQueueService

router = APIRouter(prefix="/review", tags=["review"])


@router.get("/queue", response_model=ReviewQueueResponse)
async def get_review_queue(
    user: User = Depends(current_active_user),  # noqa: B008
    session: AsyncSession = Depends(get_rls_session),  # noqa: B008
) -> ReviewQueueResponse:
    """Return the signed-in user's needs_review transactions and quarantined LLM relabels."""
    svc = ReviewQueueService(session, uuid.UUID(str(user.id)))
    return await svc.list_queue()


@router.post("/confirm", response_model=ConfirmResponse)
async def confirm_review(
    body: ConfirmRequest,
    user: User = Depends(current_active_user),  # noqa: B008
    session: AsyncSession = Depends(get_rls_session),  # noqa: B008
) -> ConfirmResponse:
    """Confirm or correct a flagged row's category (human provenance)."""
    svc = ReviewQueueService(session, uuid.UUID(str(user.id)))
    return await svc.confirm(body.transaction_id, body.category)
