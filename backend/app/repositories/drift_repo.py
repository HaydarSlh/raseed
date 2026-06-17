"""DriftRepo: insert signal snapshots, fetch latest, fetch series for charts (constitution Art. III/V)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.drift_signal import DriftSignal


class DriftRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def insert(self, signal: DriftSignal) -> DriftSignal:
        self._session.add(signal)
        await self._session.flush()
        return signal

    async def get_latest(self) -> DriftSignal | None:
        result = await self._session.execute(
            select(DriftSignal).order_by(DriftSignal.evaluated_at.desc()).limit(1)
        )
        return result.scalar_one_or_none()

    async def list_series(self, limit: int = 30) -> list[DriftSignal]:
        """Fetch recent signal snapshots ordered chronologically for chart rendering."""
        result = await self._session.execute(
            select(DriftSignal).order_by(DriftSignal.evaluated_at.desc()).limit(limit)
        )
        return list(reversed(result.scalars().all()))
