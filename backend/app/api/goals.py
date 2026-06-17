"""Goals REST: GET/POST/PATCH /goals (FR-016, contracts/http-api)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_active_user
from app.db.session import get_rls_session
from app.domain.user import User
from app.repositories.goals_repo import GoalsRepository
from app.schemas.goal import GoalCreate, GoalOut, GoalUpdate

router = APIRouter(prefix="/goals", tags=["goals"])


@router.get("", response_model=list[GoalOut])
async def list_goals(
    status: str | None = None,
    user: User = Depends(current_active_user),  # noqa: B008
    session: AsyncSession = Depends(get_rls_session),  # noqa: B008
) -> list[GoalOut]:
    repo = GoalsRepository(session, user.id)
    goals = await repo.list_by_status(status)
    return [GoalOut.model_validate(g) for g in goals]


@router.post("", response_model=GoalOut, status_code=status.HTTP_201_CREATED)
async def create_goal(
    body: GoalCreate,
    user: User = Depends(current_active_user),  # noqa: B008
    session: AsyncSession = Depends(get_rls_session),  # noqa: B008
) -> GoalOut:
    repo = GoalsRepository(session, user.id)
    goal = await repo.create(name=body.name, target_amount=body.target_amount, target_date=body.target_date)
    await session.commit()
    await session.refresh(goal)
    return GoalOut.model_validate(goal)


@router.patch("/{goal_id}", response_model=GoalOut)
async def update_goal(
    goal_id: uuid.UUID,
    body: GoalUpdate,
    user: User = Depends(current_active_user),  # noqa: B008
    session: AsyncSession = Depends(get_rls_session),  # noqa: B008
) -> GoalOut:
    repo = GoalsRepository(session, user.id)
    goal = await repo.update(goal_id, body.model_dump(exclude_none=True))
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal not found.")
    await session.commit()
    await session.refresh(goal)
    return GoalOut.model_validate(goal)
