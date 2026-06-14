"""Schema/role assertion: every user table has RLS enabled + user_id; raseed_app lacks BYPASSRLS; raseed_stats has it (FR-004, FR-007, SC-009)."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Tables that must have RLS enabled and a user_id column
_USER_TABLES = ["transactions", "goals", "corrections", "memory", "audit_log"]


@pytest.mark.asyncio
async def test_rls_enabled_on_user_tables(session: AsyncSession) -> None:
    for table in _USER_TABLES:
        row = (
            await session.execute(
                text("SELECT rowsecurity, forcerowsecurity FROM pg_class WHERE relname = :t"),
                {"t": table},
            )
        ).fetchone()
        assert row is not None, f"Table {table!r} not found in pg_class"
        rowsecurity, forcerowsecurity = row
        assert rowsecurity, f"{table}: ENABLE ROW LEVEL SECURITY not set"
        assert forcerowsecurity, f"{table}: FORCE ROW LEVEL SECURITY not set"


@pytest.mark.asyncio
async def test_user_tables_have_user_id_column(session: AsyncSession) -> None:
    for table in _USER_TABLES:
        row = (
            await session.execute(
                text("""
                    SELECT column_name FROM information_schema.columns
                    WHERE table_name = :t AND column_name = 'user_id'
                """),
                {"t": table},
            )
        ).fetchone()
        assert row is not None, f"Table {table!r} is missing a user_id column"


@pytest.mark.asyncio
async def test_rls_policy_exists_on_user_tables(session: AsyncSession) -> None:
    for table in _USER_TABLES:
        row = (
            await session.execute(
                text("SELECT policyname FROM pg_policies WHERE tablename = :t"),
                {"t": table},
            )
        ).fetchone()
        assert row is not None, f"No RLS policy found on table {table!r}"


@pytest.mark.asyncio
async def test_raseed_app_lacks_bypassrls(session: AsyncSession) -> None:
    row = (
        await session.execute(
            text("SELECT rolbypassrls FROM pg_roles WHERE rolname = 'raseed_app'")
        )
    ).fetchone()
    assert row is not None, "Role raseed_app does not exist"
    assert row[0] is False, "raseed_app must NOT have BYPASSRLS (constitution Art. II)"


@pytest.mark.asyncio
async def test_raseed_stats_has_bypassrls(session: AsyncSession) -> None:
    row = (
        await session.execute(
            text("SELECT rolbypassrls FROM pg_roles WHERE rolname = 'raseed_stats'")
        )
    ).fetchone()
    assert row is not None, "Role raseed_stats does not exist"
    assert row[0] is True, "raseed_stats must have BYPASSRLS (FR-007 — cross-user stats reader)"
