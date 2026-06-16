"""RLS isolation for Phase 3 tables: forecasts, anomalies, subscriptions.

population_stats has NO RLS and is readable by both roles; verify that too.
Uses the same conftest fixture as Phase 1 (requires a live Postgres with RLS).
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.conftest import set_user_id


@pytest.mark.asyncio
async def test_forecasts_rls_isolation(session: AsyncSession, two_users: tuple) -> None:
    user_a_id, user_b_id = two_users

    fc_a_id = uuid.uuid4()
    fc_b_id = uuid.uuid4()
    for fc_id, uid in ((fc_a_id, user_a_id), (fc_b_id, user_b_id)):
        await session.execute(
            text("""
                INSERT INTO forecasts (id, user_id, horizon_date, projected_balance, lower_bound, upper_bound)
                VALUES (:id, :uid, CURRENT_DATE + 1, 1000.0, 900.0, 1100.0)
            """),
            {"id": fc_id, "uid": uid},
        )
    await session.commit()

    await session.execute(text("SET ROLE raseed_app"))

    await set_user_id(session, str(user_a_id))
    result = await session.execute(text("SELECT id FROM forecasts"))
    ids = [r[0] for r in result.fetchall()]
    assert fc_a_id in ids
    assert fc_b_id not in ids, "User A must not see User B's forecasts"


@pytest.mark.asyncio
async def test_anomalies_rls_isolation(session: AsyncSession, two_users: tuple) -> None:
    user_a_id, user_b_id = two_users

    # We need a transaction to reference for the FK
    txn_a_id = uuid.uuid4()
    txn_b_id = uuid.uuid4()
    for txn_id, uid in ((txn_a_id, user_a_id), (txn_b_id, user_b_id)):
        await session.execute(
            text("""
                INSERT INTO transactions (id, user_id, provenance, needs_review, is_anomaly)
                VALUES (:id, :uid, 'rule', false, false)
            """),
            {"id": txn_id, "uid": uid},
        )

    a_anom_id = uuid.uuid4()
    b_anom_id = uuid.uuid4()
    for anom_id, uid, txn_id in ((a_anom_id, user_a_id, txn_a_id), (b_anom_id, user_b_id, txn_b_id)):
        await session.execute(
            text("""
                INSERT INTO anomalies (id, user_id, transaction_id, anomaly_type, reason)
                VALUES (:id, :uid, :txn_id, 'statistical_outlier', 'test')
            """),
            {"id": anom_id, "uid": uid, "txn_id": txn_id},
        )
    await session.commit()

    await session.execute(text("SET ROLE raseed_app"))
    await set_user_id(session, str(user_a_id))

    result = await session.execute(text("SELECT id FROM anomalies"))
    ids = [r[0] for r in result.fetchall()]
    assert a_anom_id in ids
    assert b_anom_id not in ids, "User A must not see User B's anomalies"


@pytest.mark.asyncio
async def test_population_stats_readable_by_all(session: AsyncSession, two_users: tuple) -> None:
    """population_stats has no RLS — any authenticated session can read it."""
    user_a_id, _ = two_users
    stat_id = uuid.uuid4()

    await session.execute(
        text("""
            INSERT INTO population_stats (id, category, day_of_week, mean_amount, stddev_amount, user_count)
            VALUES (:id, 'groceries', 0, -15.0, 3.0, 10)
        """),
        {"id": stat_id},
    )
    await session.commit()

    await session.execute(text("SET ROLE raseed_app"))
    await set_user_id(session, str(user_a_id))

    result = await session.execute(text("SELECT id FROM population_stats WHERE id = :id"), {"id": stat_id})
    assert result.fetchone() is not None, "population_stats must be readable by all sessions"
