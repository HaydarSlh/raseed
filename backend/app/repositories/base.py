"""User-scoped repository base: mandates a user_id filter on every query as defense in depth behind RLS (constitution Art. II, FR-005)."""

from __future__ import annotations

import uuid
from typing import Any, Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class UserScopedRepository(Generic[ModelT]):  # noqa: UP046
    """Base repository that always scopes queries to the current user.

    RLS is the database-layer backstop; this mandatory user filter is defense
    in depth so even an accidental unscoped ORM call at the service layer is
    caught here before it reaches the database.
    """

    model: type[ModelT]

    def __init__(self, session: AsyncSession, user_id: uuid.UUID) -> None:
        self._session = session
        self._user_id = user_id

    def _base_query(self) -> Any:
        return select(self.model).where(
            self.model.user_id == self._user_id  # type: ignore[attr-defined]
        )

    async def get_by_id(self, record_id: uuid.UUID) -> ModelT | None:
        result = await self._session.execute(
            self._base_query().where(self.model.id == record_id)  # type: ignore[attr-defined]
        )
        return result.scalar_one_or_none()

    async def list_all(self) -> list[ModelT]:
        result = await self._session.execute(self._base_query())
        return list(result.scalars().all())

    async def add(self, instance: ModelT) -> ModelT:
        if getattr(instance, "user_id", None) != self._user_id:
            raise ValueError("Cannot add a record belonging to a different user.")
        self._session.add(instance)
        await self._session.flush()
        return instance

    async def delete(self, record_id: uuid.UUID) -> bool:
        obj = await self.get_by_id(record_id)
        if obj is None:
            return False
        await self._session.delete(obj)
        await self._session.flush()
        return True
