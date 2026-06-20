"""Review queue API: GET /review/queue, POST /review/confirm — user-scoped via RLS session (constitution Art. II/III, FR-001/003)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_active_user
from app.db.session import get_rls_session
from app.domain.user import User
from app.infra.queue import get_recompute_queue
from app.schemas.review import (
    ConfirmRequest,
    ConfirmResponse,
    RelabelAllResponse,
    ReviewQueueResponse,
)
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
    response = await svc.confirm(body.transaction_id, body.category)
    # Persist the correction + needs_review=False — without this the session
    # rolls back on teardown and the row reappears in the queue on refresh.
    await session.commit()
    return response


@router.post("/relabel-all", response_model=RelabelAllResponse)
async def relabel_all(
    user: User = Depends(current_active_user),  # noqa: B008
    session: AsyncSession = Depends(get_rls_session),  # noqa: B008
) -> RelabelAllResponse:
    """Enqueue a one-shot LLM batch relabel of all the user's flagged rows.

    Results are written as quarantined llm-provenance corrections and still
    require the owning user's confirmation before they count as training data
    (constitution Art. III, FR-005/006). This is the manual trigger that the
    "LLM label all" button on the review page calls — it does not change the
    persisted review_mode the way the auto-relabel toggle does.
    """
    user_id = uuid.UUID(str(user.id))
    q = get_recompute_queue()
    q.enqueue(
        "workers.relabel.run_batch_relabel",
        kwargs={"user_id": str(user_id)},
        job_timeout=600,
    )
    return RelabelAllResponse(queued=True, user_id=user_id)
