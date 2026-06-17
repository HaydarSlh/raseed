"""Goals repository: create/list/update per-user goals with status transitions (FR-016, RLS-scoped)."""

from __future__ import annotations

import uuid
from datetime import date

from app.domain.goal import Goal, GoalStatus
from app.repositories.base import UserScopedRepository


class GoalsRepository(UserScopedRepository[Goal]):
    model = Goal

    async def create(self, *, name: str, target_amount: float, target_date: date) -> Goal:
        goal = Goal(
            user_id=self._user_id,
            name=name,
            target_amount=target_amount,
            target_date=target_date,
            status=GoalStatus.active,
        )
        self._session.add(goal)
        await self._session.flush()
        return goal

    async def list_by_status(self, status: str | None = None) -> list[Goal]:
        q = self._base_query()
        if status:
            try:
                q = q.where(Goal.status == GoalStatus(status))
            except ValueError:
                pass
        result = await self._session.execute(q.order_by(Goal.created_at.desc()))
        return list(result.scalars().all())

    async def update(self, goal_id: uuid.UUID, fields: dict) -> Goal | None:
        goal = await self.get_by_id(goal_id)
        if goal is None:
            return None
        for key, value in fields.items():
            if hasattr(goal, key):
                if key == "status":
                    setattr(goal, key, GoalStatus(value) if isinstance(value, str) else value)
                else:
                    setattr(goal, key, value)
        await self._session.flush()
        return goal
