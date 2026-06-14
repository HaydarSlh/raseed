"""RLS-scoped session dependency: sets app.user_id on the connection at request start and resets it in the finally block on teardown. Kept separate from api/deps.py so auth and persistence concerns don't collide (M2 split, constitution Art. II, SC-003)."""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_active_user
from app.domain.user import User
from app.infra.db import get_session_factory


async def get_rls_session(
    user: User = Depends(current_active_user),  # noqa: B008
) -> AsyncIterator[AsyncSession]:
    """Yield an AsyncSession with app.user_id set to the authenticated user's id.

    On teardown, resets app.user_id to '' so the pooled connection is clean for
    the next request (defense-in-depth alongside the pool reset hook in infra/db.py).
    """
    factory = get_session_factory()
    async with factory() as session:
        await session.execute(
            text("SELECT set_config('app.user_id', :uid, false)"),
            {"uid": str(user.id)},
        )
        try:
            yield session
        finally:
            await session.execute(
                text("SELECT set_config('app.user_id', '', false)")
            )
