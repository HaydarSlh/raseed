"""Integration test fixtures: real async engine/session against CI Postgres, RLS helpers, two-user seed (constitution Art. II — RLS cannot be tested without a real DB)."""

from __future__ import annotations

import os
import uuid

import pytest
import pytest_asyncio
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from alembic import command

TEST_DATABASE_URL: str = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/raseed_test",
)

_SYNC_URL = TEST_DATABASE_URL.replace("+asyncpg", "+psycopg2")


@pytest.fixture(scope="session")
def run_migrations() -> None:
    """Apply all Alembic migrations to the test database (session-scoped, runs once)."""
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", _SYNC_URL)
    command.upgrade(cfg, "head")


@pytest_asyncio.fixture(scope="session")
async def engine(run_migrations: None):
    eng = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine):  # noqa: ANN001
    """A plain session — NOT RLS-scoped; used for seeding data as superuser."""
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s


async def set_user_id(session: AsyncSession, user_id: str | None) -> None:
    """Helper: set or clear app.user_id on the current connection."""
    uid = user_id or ""
    await session.execute(
        text("SELECT set_config('app.user_id', :uid, false)"), {"uid": uid}
    )


async def clear_user_id(session: AsyncSession) -> None:
    await set_user_id(session, "")


@pytest_asyncio.fixture
async def two_users(session: AsyncSession):
    """Seed two users and their IDs; yield (user_a_id, user_b_id); clean up after."""
    user_a_id = uuid.uuid4()
    user_b_id = uuid.uuid4()
    await session.execute(
        text("""
            INSERT INTO users (id, email, hashed_password, is_active, is_superuser, is_verified, is_operator)
            VALUES
              (:a_id, 'user_a@test.com', '$bcrypt$hashed', true, false, false, false),
              (:b_id, 'user_b@test.com', '$bcrypt$hashed', true, false, false, false)
        """),
        {"a_id": user_a_id, "b_id": user_b_id},
    )
    await session.commit()
    yield user_a_id, user_b_id
    await session.execute(
        text("DELETE FROM users WHERE id IN (:a_id, :b_id)"),
        {"a_id": user_a_id, "b_id": user_b_id},
    )
    await session.commit()
