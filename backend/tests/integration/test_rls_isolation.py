"""RLS isolation: own-rows-only, deliberately unscoped query returns zero foreign rows, write blocked by WITH CHECK (contracts/rls-tenancy.md, FR-005, SC-002)."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import exc as sqla_exc
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.conftest import clear_user_id, set_user_id


@pytest.mark.asyncio
async def test_own_rows_only(session: AsyncSession, two_users: tuple) -> None:
    user_a_id, user_b_id = two_users

    # Seed a goal for each user (as superuser — no RLS active yet)
    goal_a_id = uuid.uuid4()
    goal_b_id = uuid.uuid4()
    await session.execute(
        text("INSERT INTO goals (id, user_id, name) VALUES (:id, :uid, :name)"),
        {"id": goal_a_id, "uid": user_a_id, "name": "Goal A"},
    )
    await session.execute(
        text("INSERT INTO goals (id, user_id, name) VALUES (:id, :uid, :name)"),
        {"id": goal_b_id, "uid": user_b_id, "name": "Goal B"},
    )
    await session.commit()

    # SET ROLE to raseed_app so RLS policies bind
    await session.execute(text("SET ROLE raseed_app"))

    # Under user A's context: only A's goal visible
    await set_user_id(session, str(user_a_id))
    result = await session.execute(text("SELECT id FROM goals"))
    rows = [r[0] for r in result.fetchall()]
    assert goal_a_id in rows
    assert goal_b_id not in rows, "User A must not see User B's goal"

    # Deliberately UNSCOPED query — RLS still catches it (the headline test SC-002)
    result = await session.execute(text("SELECT id FROM goals WHERE TRUE"))
    unscoped_rows = [r[0] for r in result.fetchall()]
    assert goal_b_id not in unscoped_rows, "Unscoped query must not leak User B's goal to User A"

    await clear_user_id(session)
    await session.execute(text("RESET ROLE"))
    # Cleanup
    await session.execute(text("DELETE FROM goals WHERE id IN (:a, :b)"), {"a": goal_a_id, "b": goal_b_id})
    await session.commit()


@pytest.mark.asyncio
async def test_write_isolation(session: AsyncSession, two_users: tuple) -> None:
    """Attempt to INSERT a goal with user_b's user_id while running as user_a; WITH CHECK rejects it."""
    user_a_id, user_b_id = two_users

    await session.execute(text("SET ROLE raseed_app"))
    await set_user_id(session, str(user_a_id))

    bad_id = uuid.uuid4()
    with pytest.raises(sqla_exc.DBAPIError):  # RLS WITH CHECK violation
        await session.execute(
            text("INSERT INTO goals (id, user_id, name) VALUES (:id, :uid, :name)"),
            {"id": bad_id, "uid": user_b_id, "name": "Smuggled"},
        )
        await session.flush()

    await session.rollback()
    await session.execute(text("RESET ROLE"))
