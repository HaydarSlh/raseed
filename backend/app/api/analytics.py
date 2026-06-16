"""Analytics read endpoints: /dashboard, /forecast, /anomalies, /subscriptions.

Pure DB reads — no model-server calls, no Prophet fits on the request path
(constitution Art. V, R7). Reads are already computed by the recompute worker;
this router just fetches and serialises the stored rows.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_active_user
from app.domain.user import User
from app.infra.db import get_session_factory
from app.repositories.analytics_repo import (
    AnomalyRepository,
    ForecastRepository,
    SubscriptionRepository,
)
from app.repositories.transactions_repo import TransactionsRepository

router = APIRouter(tags=["analytics"])


async def _rls_session(user: User = Depends(current_active_user)) -> AsyncSession:  # type: ignore[misc]
    import sqlalchemy as sa

    factory = get_session_factory()
    async with factory() as session:
        await session.execute(
            sa.text("SELECT set_config('app.user_id', :uid, true)"),
            {"uid": str(user.id)},
        )
        yield session


# ─── Response models ──────────────────────────────────────────────────────────

class TransactionOut(BaseModel):
    id: uuid.UUID
    txn_date: datetime | None
    amount: float | None
    category: str | None
    confidence: float | None
    provenance: str
    needs_review: bool
    is_anomaly: bool


class ForecastPoint(BaseModel):
    date: date
    projected_balance: float
    lower: float
    upper: float


class ForecastOut(BaseModel):
    horizon_days: int
    is_cold_start: bool
    points: list[ForecastPoint]


class AnomalyOut(BaseModel):
    transaction_id: uuid.UUID
    anomaly_type: str
    reason: str


class SubscriptionOut(BaseModel):
    merchant: str
    cadence: str
    typical_amount: float
    next_charge_date: date | None
    price_increase: bool


class DashboardOut(BaseModel):
    transactions: list[TransactionOut]
    forecast: ForecastOut
    anomalies: list[AnomalyOut]
    subscriptions: list[SubscriptionOut]


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _empty_forecast() -> ForecastOut:
    return ForecastOut(horizon_days=30, is_cold_start=True, points=[])


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.get("/dashboard", response_model=DashboardOut)
async def get_dashboard(
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(_rls_session),
) -> DashboardOut:
    """Return aggregated dashboard payload; all reads are parallelised."""
    txn_repo = TransactionsRepository(session, user.id)
    forecast_repo = ForecastRepository(session, user.id)
    anomaly_repo = AnomalyRepository(session, user.id)
    sub_repo = SubscriptionRepository(session, user.id)

    transactions, forecast_rows, anomaly_rows, sub_rows = await asyncio.gather(
        txn_repo.list_all(),
        forecast_repo.list_all(),
        anomaly_repo.list_all(),
        sub_repo.list_all(),
    )

    txn_out = [
        TransactionOut(
            id=t.id,
            txn_date=t.occurred_at,
            amount=float(t.amount) if t.amount is not None else None,
            category=t.category,
            confidence=t.confidence,
            provenance=t.provenance.value,
            needs_review=t.needs_review,
            is_anomaly=t.is_anomaly,
        )
        for t in transactions
    ]

    cold_start = any(f.is_cold_start for f in forecast_rows)
    forecast_out = ForecastOut(
        horizon_days=30,
        is_cold_start=cold_start,
        points=[
            ForecastPoint(
                date=f.horizon_date,
                projected_balance=float(f.projected_balance),
                lower=float(f.lower_bound),
                upper=float(f.upper_bound),
            )
            for f in sorted(forecast_rows, key=lambda r: r.horizon_date)
        ],
    ) if forecast_rows else _empty_forecast()

    anomaly_out = [
        AnomalyOut(
            transaction_id=a.transaction_id,
            anomaly_type=a.anomaly_type.value,
            reason=a.reason,
        )
        for a in anomaly_rows
    ]

    sub_out = [
        SubscriptionOut(
            merchant=s.merchant,
            cadence=s.cadence.value,
            typical_amount=float(s.typical_amount),
            next_charge_date=s.next_charge_date,
            price_increase=s.price_increase,
        )
        for s in sub_rows
    ]

    return DashboardOut(
        transactions=txn_out,
        forecast=forecast_out,
        anomalies=anomaly_out,
        subscriptions=sub_out,
    )


@router.get("/forecast", response_model=ForecastOut)
async def get_forecast(
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(_rls_session),
) -> ForecastOut:
    repo = ForecastRepository(session, user.id)
    rows = await repo.list_all()
    if not rows:
        return _empty_forecast()
    cold_start = any(r.is_cold_start for r in rows)
    return ForecastOut(
        horizon_days=30,
        is_cold_start=cold_start,
        points=[
            ForecastPoint(
                date=r.horizon_date,
                projected_balance=float(r.projected_balance),
                lower=float(r.lower_bound),
                upper=float(r.upper_bound),
            )
            for r in sorted(rows, key=lambda r: r.horizon_date)
        ],
    )


@router.get("/anomalies", response_model=list[AnomalyOut])
async def get_anomalies(
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(_rls_session),
) -> list[AnomalyOut]:
    repo = AnomalyRepository(session, user.id)
    rows = await repo.list_all()
    return [
        AnomalyOut(transaction_id=a.transaction_id, anomaly_type=a.anomaly_type.value, reason=a.reason)
        for a in rows
    ]


@router.get("/subscriptions", response_model=list[SubscriptionOut])
async def get_subscriptions(
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(_rls_session),
) -> list[SubscriptionOut]:
    repo = SubscriptionRepository(session, user.id)
    rows = await repo.list_all()
    return [
        SubscriptionOut(
            merchant=s.merchant,
            cadence=s.cadence.value,
            typical_amount=float(s.typical_amount),
            next_charge_date=s.next_charge_date,
            price_increase=s.price_increase,
        )
        for s in rows
    ]
