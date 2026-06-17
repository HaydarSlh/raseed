"""Corrections repository: write human corrections, list quarantined rows, count confirmed-since-retrain (constitution Art. III — only human-confirmed rows train)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.correction import Correction, CorrectionProvenance


class CorrectionsRepository:
    def __init__(self, session: AsyncSession, user_id: uuid.UUID) -> None:
        self._session = session
        self._user_id = user_id

    async def write_correction(self, correction: Correction) -> Correction:
        """Persist a correction row (human or llm-quarantined)."""
        self._session.add(correction)
        await self._session.flush()
        return correction

    async def get_by_transaction(self, transaction_id: uuid.UUID) -> Correction | None:
        result = await self._session.execute(
            select(Correction)
            .where(Correction.user_id == self._user_id)
            .where(Correction.transaction_id == transaction_id)
            .order_by(Correction.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_quarantined(self) -> list[Correction]:
        """Return this user's LLM-relabeled rows awaiting human confirmation."""
        result = await self._session.execute(
            select(Correction)
            .where(Correction.user_id == self._user_id)
            .where(Correction.quarantined == True)  # noqa: E712
            .order_by(Correction.created_at.desc())
        )
        return list(result.scalars().all())

    async def confirm_correction(self, correction_id: uuid.UUID, new_category: str, confirmed_at: datetime) -> Correction | None:
        """Upgrade a quarantined LLM correction to human-confirmed."""
        result = await self._session.execute(
            select(Correction)
            .where(Correction.id == correction_id)
            .where(Correction.user_id == self._user_id)
        )
        correction = result.scalar_one_or_none()
        if correction is None:
            return None
        correction.new_category = new_category
        correction.provenance = CorrectionProvenance.human
        correction.quarantined = False
        correction.confirmed_by_human = True
        correction.confirmed_at = confirmed_at
        await self._session.flush()
        return correction

    async def count_confirmed_since(self, since: datetime) -> int:
        """Count human-confirmed corrections created after `since` (for retrain trigger)."""
        result = await self._session.execute(
            select(func.count())
            .select_from(Correction)
            .where(Correction.confirmed_by_human == True)  # noqa: E712
            .where(Correction.created_at > since)
        )
        return int(result.scalar_one() or 0)
