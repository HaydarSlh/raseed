"""Async SQLAlchemy engine + session factory; pool-reset hook wipes app.user_id on connection release so pooled connections never carry identity into the next request (constitution Art. II, SC-003)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_engine(database_url: str) -> AsyncEngine:
    global _engine, _session_factory
    engine = create_async_engine(database_url, pool_pre_ping=True)

    @event.listens_for(engine.sync_engine, "reset")
    def _reset_app_user_id(dbapi_conn: Any, connection_record: Any, reset_state: Any) -> None:
        """Pool reset hook: clear app.user_id so no identity bleeds into the next request checkout."""
        cursor = dbapi_conn.cursor()
        cursor.execute("SELECT set_config('app.user_id', '', false)")
        cursor.close()

    _engine = engine
    _session_factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine


def get_engine() -> AsyncEngine:
    assert _engine is not None, "Engine not initialised — call init_engine() in lifespan"
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    assert _session_factory is not None, "Session factory not initialised — call init_engine() in lifespan"
    return _session_factory


async def get_async_session() -> AsyncIterator[AsyncSession]:
    """Plain session dep for auth operations (users table has no RLS — no user_id needed)."""
    factory = get_session_factory()
    async with factory() as session:
        yield session


async def dispose_engine() -> None:
    if _engine is not None:
        await _engine.dispose()
