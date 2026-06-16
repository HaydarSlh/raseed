"""Transactions repository: user-scoped reads/writes with insert-skip-on-dedup-conflict and
the anomaly-flag update used by the recompute worker (constitution Art. II — RLS + mandatory
user filter as defense in depth)."""

from __future__ import annotations

import uuid

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.domain.transaction import Transaction
from app.repositories.base import UserScopedRepository


class TransactionsRepository(UserScopedRepository[Transaction]):
    model = Transaction

    async def insert_skip_duplicates(self, rows: list[dict]) -> int:
        """Insert enriched rows, skipping any matching the dedup natural key.

        Each dict must carry `user_id == self._user_id`. Returns the number actually
        inserted (duplicates silently skipped via ON CONFLICT DO NOTHING).
        """
        if not rows:
            return 0
        for r in rows:
            if r.get("user_id") != self._user_id:
                raise ValueError("Cannot insert a transaction for a different user.")
        stmt = (
            pg_insert(Transaction)
            .values(rows)
            .on_conflict_do_nothing(index_elements=["user_id", "occurred_at", "amount", "normalized_description"])
            .returning(Transaction.id)
        )
        result = await self._session.execute(stmt)
        inserted = len(list(result.scalars().all()))
        await self._session.flush()
        return inserted

    async def set_anomaly_flags(self, anomalous_ids: set[uuid.UUID]) -> None:
        """Reset is_anomaly for the user, then flag the given transactions (recompute)."""
        await self._session.execute(
            update(Transaction)
            .where(Transaction.user_id == self._user_id)
            .values(is_anomaly=False)
        )
        if anomalous_ids:
            await self._session.execute(
                update(Transaction)
                .where(Transaction.user_id == self._user_id, Transaction.id.in_(anomalous_ids))
                .values(is_anomaly=True)
            )
        await self._session.flush()
