"""Per-user analytics recompute worker: forecast + anomaly + subscription detection.

Triggered via the RQ 'default' queue after every transaction write (invalidate-on-write,
constitution Art. V). Heavy deps (Prophet) load here — never in the lean model-server
image (constitution Art. III).
"""

from __future__ import annotations

import asyncio
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db import get_async_sessionmaker
from app.repositories.analytics_repo import (
    AnomalyRepository,
    ForecastRepository,
    SubscriptionRepository,
)
from app.repositories.transactions_repo import TransactionsRepository
from app.services.analytics import (
    compute_forecast,
    detect_anomalies,
    detect_subscriptions,
)


async def _run_async(user_id: uuid.UUID) -> None:
    session_factory = get_async_sessionmaker()
    async with session_factory() as session:
        async with session.begin():
            await _recompute(session, user_id)


async def _recompute(session: AsyncSession, user_id: uuid.UUID) -> None:
    txn_repo = TransactionsRepository(session, user_id)
    forecast_repo = ForecastRepository(session, user_id)
    anomaly_repo = AnomalyRepository(session, user_id)
    sub_repo = SubscriptionRepository(session, user_id)

    transactions = await txn_repo.list_all()

    # Anomaly detection first (also produces the anomalous_id set for flagging)
    anomalies, anomalous_ids = detect_anomalies(user_id, transactions)
    await anomaly_repo.replace_all(anomalies)
    await txn_repo.set_anomaly_flags(anomalous_ids)

    # Recurring charges
    subscriptions = detect_subscriptions(user_id, transactions)
    await sub_repo.replace_all(subscriptions)

    # Forecast
    forecasts = compute_forecast(user_id, transactions)
    await forecast_repo.replace_all(forecasts)


def run(user_id: str) -> None:
    """RQ entry point: called by the light worker with user_id as a string."""
    asyncio.run(_run_async(uuid.UUID(user_id)))
