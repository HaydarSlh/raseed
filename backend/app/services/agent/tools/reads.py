"""Read tools: query_transactions, get_forecast, get_anomalies, get_subscriptions (contracts/tools, R8)."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.analytics import Anomaly, Forecast, Subscription
from app.domain.transaction import Transaction
from app.services.agent.tools.registry import register_tool

# These tools need an RLS-scoped session + user_id injected at dispatch time.
# The registry's dispatch() passes **validated.model_dump(), so we define
# _session and _user_id as optional fields with None defaults that are
# injected by the agent loop via a session-injection wrapper.
# For now they accept them as plain kwargs; the loop wraps each call.


class QueryTransactionsInput(BaseModel):
    category: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    limit: int | None = Field(None, le=100)
    # Injected by loop wrapper
    _session: object | None = None
    _user_id: uuid.UUID | None = None

    model_config = {"arbitrary_types_allowed": True}


class GetForecastInput(BaseModel):
    horizon_days: int | None = Field(None, ge=1, le=365)


class GetAnomaliesInput(BaseModel):
    limit: int | None = Field(None, le=50)


class GetSubscriptionsInput(BaseModel):
    pass


async def query_transactions(
    category: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int | None = None,
    _session: AsyncSession | None = None,
    _user_id: uuid.UUID | None = None,
) -> dict:
    if _session is None or _user_id is None:
        return {"error": "Session context not available"}
    q = select(Transaction).where(Transaction.user_id == _user_id)
    if category:
        q = q.where(Transaction.category.ilike(f"%{category}%"))
    if start_date:
        q = q.where(Transaction.occurred_at >= datetime.combine(start_date, datetime.min.time()))
    if end_date:
        q = q.where(Transaction.occurred_at <= datetime.combine(end_date, datetime.max.time()))
    if limit:
        q = q.limit(limit)
    result = await _session.execute(q)
    rows = result.scalars().all()
    total = sum(float(r.amount or 0) for r in rows)
    items = [{"date": str(r.occurred_at.date()) if r.occurred_at else None, "amount": float(r.amount or 0), "category": r.category} for r in rows]
    return {"count": len(items), "total_amount": total, "items": items}


async def get_forecast(
    horizon_days: int | None = None,
    _session: AsyncSession | None = None,
    _user_id: uuid.UUID | None = None,
) -> dict:
    if _session is None or _user_id is None:
        return {"error": "Session context not available"}
    q = select(Forecast).where(Forecast.user_id == _user_id).order_by(Forecast.horizon_date)
    if horizon_days:
        from datetime import date as dt
        from datetime import timedelta
        cutoff = dt.today() + timedelta(days=horizon_days)
        q = q.where(Forecast.horizon_date <= cutoff)
    result = await _session.execute(q)
    rows = result.scalars().all()
    is_cold = all(r.is_cold_start for r in rows) if rows else True
    points = [{"date": str(r.horizon_date), "projected_balance": float(r.projected_balance)} for r in rows]
    return {"is_cold_start": is_cold, "horizon_days": horizon_days or 30, "points": points}


async def get_anomalies(
    limit: int | None = None,
    _session: AsyncSession | None = None,
    _user_id: uuid.UUID | None = None,
) -> dict:
    if _session is None or _user_id is None:
        return {"error": "Session context not available"}
    q = select(Anomaly).where(Anomaly.user_id == _user_id).order_by(Anomaly.computed_at.desc())
    if limit:
        q = q.limit(limit)
    result = await _session.execute(q)
    rows = result.scalars().all()
    items = [{"anomaly_type": r.anomaly_type.value, "reason": r.reason} for r in rows]
    return {"items": items}


async def get_subscriptions(
    _session: AsyncSession | None = None,
    _user_id: uuid.UUID | None = None,
) -> dict:
    if _session is None or _user_id is None:
        return {"error": "Session context not available"}
    result = await _session.execute(select(Subscription).where(Subscription.user_id == _user_id))
    rows = result.scalars().all()
    items = [
        {
            "merchant": r.merchant,
            "cadence": r.cadence.value,
            "typical_amount": float(r.typical_amount),
            "next_charge_date": str(r.next_charge_date) if r.next_charge_date else None,
            "price_increase": r.price_increase,
        }
        for r in rows
    ]
    return {"items": items}


register_tool("query_transactions", QueryTransactionsInput, query_transactions)
register_tool("get_forecast", GetForecastInput, get_forecast)
register_tool("get_anomalies", GetAnomaliesInput, get_anomalies)
register_tool("get_subscriptions", GetSubscriptionsInput, get_subscriptions)
