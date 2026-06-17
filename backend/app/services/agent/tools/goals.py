"""Goal tools: get_goals, set_goal (FR-016, contracts/tools)."""

from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.agent.tools.registry import register_tool


class GetGoalsInput(BaseModel):
    status: str | None = None
    _session: object | None = None
    _user_id: uuid.UUID | None = None

    model_config = {"arbitrary_types_allowed": True}


class SetGoalInput(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)
    target_amount: float = Field(..., gt=0)
    target_date: date
    id: uuid.UUID | None = None
    status: str | None = None
    _session: object | None = None
    _user_id: uuid.UUID | None = None

    model_config = {"arbitrary_types_allowed": True}


async def get_goals(
    status: str | None = None,
    _session: AsyncSession | None = None,
    _user_id: uuid.UUID | None = None,
) -> dict:
    if _session is None or _user_id is None:
        return {"error": "Session context not available"}
    from app.repositories.goals_repo import GoalsRepository
    repo = GoalsRepository(_session, _user_id)
    goals = await repo.list_by_status(status)
    return {
        "items": [
            {
                "id": str(g.id),
                "name": g.name,
                "target_amount": float(g.target_amount),
                "target_date": str(g.target_date),
                "status": g.status.value,
            }
            for g in goals
        ]
    }


async def set_goal(
    name: str,
    target_amount: float,
    target_date: date,
    id: uuid.UUID | None = None,
    status: str | None = None,
    _session: AsyncSession | None = None,
    _user_id: uuid.UUID | None = None,
) -> dict:
    if _session is None or _user_id is None:
        return {"error": "Session context not available"}
    from app.core.config import get_settings
    from app.repositories.goals_repo import GoalsRepository
    from app.services.agent.ratelimit import check_write_rate

    settings = get_settings()
    await check_write_rate(_user_id, limit=settings.write_rate_per_min)

    repo = GoalsRepository(_session, _user_id)
    if id:
        fields: dict = {"name": name, "target_amount": target_amount, "target_date": target_date}
        if status:
            fields["status"] = status
        goal = await repo.update(id, fields)
        if goal is None:
            return {"error": "Goal not found"}
    else:
        goal = await repo.create(name=name, target_amount=target_amount, target_date=target_date)
    await _session.flush()
    return {
        "id": str(goal.id),
        "name": goal.name,
        "target_amount": float(goal.target_amount),
        "target_date": str(goal.target_date),
        "status": goal.status.value,
    }


register_tool("get_goals", GetGoalsInput, get_goals)
register_tool("set_goal", SetGoalInput, set_goal)
