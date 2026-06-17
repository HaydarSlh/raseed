"""RetrainRuns repository: create/update retrain runs, fetch history, idempotency-key guard (constitution Art. III)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.retrain_run import RetrainRun, RunStatus, TriggerReason


class RetrainRunsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, run: RetrainRun) -> RetrainRun:
        """Create a new retrain run. Raises IntegrityError on duplicate idempotency_key."""
        self._session.add(run)
        await self._session.flush()
        return run

    async def get_by_idempotency_key(self, key: str) -> RetrainRun | None:
        result = await self._session.execute(
            select(RetrainRun).where(RetrainRun.idempotency_key == key)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, run_id: uuid.UUID) -> RetrainRun | None:
        result = await self._session.execute(
            select(RetrainRun).where(RetrainRun.id == run_id)
        )
        return result.scalar_one_or_none()

    async def get_latest(self) -> RetrainRun | None:
        result = await self._session.execute(
            select(RetrainRun).order_by(RetrainRun.created_at.desc()).limit(1)
        )
        return result.scalar_one_or_none()

    async def list_history(self, limit: int = 20) -> list[RetrainRun]:
        result = await self._session.execute(
            select(RetrainRun).order_by(RetrainRun.created_at.desc()).limit(limit)
        )
        return list(result.scalars().all())

    async def update_status(
        self,
        run_id: uuid.UUID,
        status: RunStatus,
        *,
        completed_at: datetime | None = None,
        challenger_id: uuid.UUID | None = None,
        champion_macro_f1: float | None = None,
        challenger_macro_f1: float | None = None,
        gate_verdict: str | None = None,
        labels_used: int | None = None,
        skipped_reason: str | None = None,
    ) -> RetrainRun | None:
        run = await self.get_by_id(run_id)
        if run is None:
            return None
        run.status = status
        if completed_at is not None:
            run.completed_at = completed_at
        if challenger_id is not None:
            run.challenger_id = challenger_id
        if champion_macro_f1 is not None:
            run.champion_macro_f1 = champion_macro_f1
        if challenger_macro_f1 is not None:
            run.challenger_macro_f1 = challenger_macro_f1
        if gate_verdict is not None:
            run.gate_verdict = gate_verdict
        if labels_used is not None:
            run.labels_used = labels_used
        if skipped_reason is not None:
            run.skipped_reason = skipped_reason
        await self._session.flush()
        return run

    async def create_or_get(self, idempotency_key: str, trigger_reason: TriggerReason) -> tuple[RetrainRun, bool]:
        """Create a new run or return an existing one with the same idempotency key.

        Returns (run, created) where created=False if the key already existed.
        """
        existing = await self.get_by_idempotency_key(idempotency_key)
        if existing is not None:
            return existing, False
        run = RetrainRun(
            idempotency_key=idempotency_key,
            trigger_reason=trigger_reason,
            status=RunStatus.enqueued,
        )
        try:
            run = await self.create(run)
        except IntegrityError:
            await self._session.rollback()
            existing = await self.get_by_idempotency_key(idempotency_key)
            return existing, False  # type: ignore[return-value]
        return run, True
