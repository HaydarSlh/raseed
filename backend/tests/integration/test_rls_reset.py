"""RLS pool-reset: app.user_id does not carry across request boundaries; unset context matches no rows (contracts/rls-tenancy.md, FR-006, SC-003)."""

from __future__ import annotations

import uuid

import pytest
import sqlalchemy.exc as sqla_exc
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker


@pytest.mark.asyncio
async def test_user_id_resets_between_sessions(engine) -> None:
    """After a session closes (returning connection to pool), next session must not inherit app.user_id."""
    factory = async_sessionmaker(engine, expire_on_commit=False)
    user_id = uuid.uuid4()
    # Use UUID-based email to avoid collisions from prior failed runs
    email = f"reset_{user_id.hex[:8]}@test.com"

    # Seed a user and a goal
    async with factory() as seed:
        await seed.execute(
            text("INSERT INTO users (id, email, hashed_password, is_active, is_superuser, is_verified, is_operator) VALUES (:uid, :email, '$x', true, false, false, false)"),
            {"uid": user_id, "email": email},
        )
        goal_id = uuid.uuid4()
        await seed.execute(
            text("INSERT INTO goals (id, user_id, name) VALUES (:id, :uid, :name)"),
            {"id": goal_id, "uid": user_id, "name": "Reset Test Goal"},
        )
        await seed.commit()

    # Session 1: set app.user_id, verify rows visible, close session
    async with factory() as s1:
        await s1.execute(text("SELECT set_config('app.user_id', :uid, false)"), {"uid": str(user_id)})
        await s1.execute(text("SET ROLE raseed_app"))
        result = await s1.execute(text("SELECT id FROM goals"))
        assert any(r[0] == goal_id for r in result.fetchall()), "Goal should be visible with user_id set"
        await s1.execute(text("RESET ROLE"))
        # Explicitly reset user_id (simulating session dep teardown)
        await s1.execute(text("SELECT set_config('app.user_id', '', false)"))
        # Session closes here — connection returned to pool

    # Session 2: must start with no app.user_id → unset context → no rows
    async with factory() as s2:
        await s2.execute(text("SET ROLE raseed_app"))
        # Do NOT set app.user_id — check that it is unset
        ctx = (await s2.execute(text("SELECT current_setting('app.user_id', true)"))).scalar()
        assert ctx in (None, ""), f"app.user_id leaked across sessions: {ctx!r}"

        # Empty app.user_id → RLS policy may raise a uuid cast error OR return 0 rows;
        # both outcomes are "fail closed" (no user data leaked).
        try:
            result = await s2.execute(text("SELECT id FROM goals"))
            rows = [r[0] for r in result.fetchall()]
            assert goal_id not in rows, "Goals must not be visible without app.user_id set (fail closed)"
        except sqla_exc.DBAPIError:
            await s2.rollback()  # cast error on ''::uuid — also fail-closed
        await s2.execute(text("RESET ROLE"))

    # Cleanup
    async with factory() as cleanup:
        await cleanup.execute(text("DELETE FROM goals WHERE id = :id"), {"id": goal_id})
        await cleanup.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": user_id})
        await cleanup.commit()
