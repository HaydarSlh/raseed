"""Analysis tools: affordability_check, what_if — compose reads + arithmetic (contracts/tools, FR-011)."""

from __future__ import annotations

import uuid
from datetime import date, timedelta

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.agent.tools.registry import register_tool


class AffordabilityInput(BaseModel):
    amount: float = Field(..., gt=0)
    when: date | None = None
    goal_id: uuid.UUID | None = None
    _session: object | None = None
    _user_id: uuid.UUID | None = None

    model_config = {"arbitrary_types_allowed": True}


class WhatIfChange(BaseModel):
    category: str | None = None
    monthly_delta: float


class WhatIfInput(BaseModel):
    change: WhatIfChange
    _session: object | None = None
    _user_id: uuid.UUID | None = None

    model_config = {"arbitrary_types_allowed": True}


async def affordability_check(
    amount: float,
    when: date | None = None,
    goal_id: uuid.UUID | None = None,
    _session: AsyncSession | None = None,
    _user_id: uuid.UUID | None = None,
) -> dict:
    """Compose forecast + recent spend + optional goal to answer affordability (FR-011, US3)."""
    if _session is None or _user_id is None:
        return {"error": "Session context not available"}

    from app.domain.analytics import Forecast
    from app.domain.transaction import Transaction
    from app.repositories.goals_repo import GoalsRepository

    target_date = when or (date.today() + timedelta(days=30))

    # 1. Get projected balance at target_date
    result = await _session.execute(
        select(Forecast)
        .where(Forecast.user_id == _user_id, Forecast.horizon_date <= target_date)
        .order_by(Forecast.horizon_date.desc())
        .limit(1)
    )
    forecast_row = result.scalar_one_or_none()
    projected = float(forecast_row.projected_balance) if forecast_row else None

    # 2. Compute recent monthly spend
    thirty_days_ago = date.today() - timedelta(days=30)
    result2 = await _session.execute(
        select(func.coalesce(func.sum(Transaction.amount), 0))
        .where(
            Transaction.user_id == _user_id,
            Transaction.occurred_at >= thirty_days_ago,
            Transaction.amount < 0,
        )
    )
    monthly_spend = abs(float(result2.scalar_one() or 0))

    # 3. Goal impact (optional)
    goal_impact = None
    if goal_id:
        repo = GoalsRepository(_session, _user_id)
        goal = await repo.get_by_id(goal_id)
        if goal:
            # Simple heuristic: is projected balance enough to cover amount + goal?
            deficit = (projected or 0) - amount - float(goal.target_amount)
            goal_impact = {
                "goal_name": goal.name,
                "on_track": deficit >= 0,
            }

    affordable = projected is not None and (projected - amount) >= 0
    rationale_parts = [f"Your projected balance on {target_date} is £{projected:,.2f}." if projected is not None else "No forecast available."]
    rationale_parts.append(f"Your recent monthly spend is £{monthly_spend:,.2f}.")
    if goal_impact:
        track = "on track" if goal_impact["on_track"] else "at risk"
        rationale_parts.append(f"Your goal '{goal_impact['goal_name']}' would be {track} after this purchase.")

    return {
        "affordable": affordable,
        "projected_balance_at_when": projected,
        "goal_impact": goal_impact,
        "rationale": " ".join(rationale_parts),
    }


async def what_if(
    change: WhatIfChange | dict,
    _session: AsyncSession | None = None,
    _user_id: uuid.UUID | None = None,
) -> dict:
    """Recompute a balance projection under a hypothetical spend change (read-only)."""
    if _session is None or _user_id is None:
        return {"error": "Session context not available"}

    if isinstance(change, dict):
        change = WhatIfChange(**change)

    from app.domain.analytics import Forecast

    result = await _session.execute(
        select(Forecast).where(Forecast.user_id == _user_id).order_by(Forecast.horizon_date)
    )
    rows = result.scalars().all()

    # Apply the delta to each projected day
    daily_delta = change.monthly_delta / 30.0
    adjusted = [
        {"date": str(r.horizon_date), "projected_balance": float(r.projected_balance) + daily_delta * (i + 1)}
        for i, r in enumerate(rows)
    ]

    direction = "increase" if change.monthly_delta > 0 else "decrease"
    summary = f"If you {direction} spending on {change.category or 'all categories'} by £{abs(change.monthly_delta):,.2f}/month, your projected balance adjusts accordingly."

    return {"adjusted_projection": adjusted, "summary": summary}


register_tool("affordability_check", AffordabilityInput, affordability_check)
register_tool("what_if", WhatIfInput, what_if)
