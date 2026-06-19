"""User settings API: GET/PUT /settings/review-mode (constitution Art. II — user-scoped)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_active_user
from app.db.session import get_rls_session
from app.domain.user import User
from app.domain.user_settings import ReviewMode, UserSettings
from app.infra.queue import get_recompute_queue
from app.schemas.review import ReviewModeRequest, ReviewModeResponse

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/review-mode", response_model=ReviewModeResponse)
async def get_review_mode(
    user: User = Depends(current_active_user),  # noqa: B008
    session: AsyncSession = Depends(get_rls_session),  # noqa: B008
) -> ReviewModeResponse:
    result = await session.execute(
        select(UserSettings).where(UserSettings.user_id == uuid.UUID(str(user.id)))
    )
    settings_row = result.scalar_one_or_none()
    mode = settings_row.review_mode.value if settings_row else ReviewMode.manual.value
    return ReviewModeResponse(review_mode=mode)


@router.put("/review-mode", response_model=ReviewModeResponse)
async def put_review_mode(
    body: ReviewModeRequest,
    user: User = Depends(current_active_user),  # noqa: B008
    session: AsyncSession = Depends(get_rls_session),  # noqa: B008
) -> ReviewModeResponse:
    try:
        mode = ReviewMode(body.review_mode)
    except ValueError as exc:
        from app.core.exceptions import ValidationError
        raise ValidationError(f"Invalid review_mode: {body.review_mode!r}") from exc

    user_id = uuid.UUID(str(user.id))
    result = await session.execute(select(UserSettings).where(UserSettings.user_id == user_id))
    settings_row = result.scalar_one_or_none()
    if settings_row is None:
        settings_row = UserSettings(user_id=user_id, review_mode=mode)
        session.add(settings_row)
    else:
        settings_row.review_mode = mode

    if mode == ReviewMode.auto_relabel:
        # Enqueue a batch relabel job for existing flagged rows (non-blocking)
        q = get_recompute_queue()
        q.enqueue(
            "workers.relabel.run_batch_relabel",
            kwargs={"user_id": str(user_id)},
            job_timeout=600,
        )

    await session.commit()
    return ReviewModeResponse(review_mode=mode.value)
