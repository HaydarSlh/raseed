"""ModelRegistry repository: champion lookup, list promotable challengers, atomic promotion swap (constitution Art. III)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.model_registry import ModelRegistry, ModelStatus


class ModelRegistryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_champion(self) -> ModelRegistry | None:
        result = await self._session.execute(
            select(ModelRegistry).where(ModelRegistry.status == ModelStatus.champion)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, model_id: uuid.UUID) -> ModelRegistry | None:
        result = await self._session.execute(
            select(ModelRegistry).where(ModelRegistry.id == model_id)
        )
        return result.scalar_one_or_none()

    async def list_promotable(self) -> list[ModelRegistry]:
        """Return challengers that have beaten the champion (gate_verdict via retrain_run)."""
        result = await self._session.execute(
            select(ModelRegistry).where(ModelRegistry.status == ModelStatus.challenger)
        )
        return list(result.scalars().all())

    async def create(self, entry: ModelRegistry) -> ModelRegistry:
        self._session.add(entry)
        await self._session.flush()
        return entry

    async def promote(self, challenger_id: uuid.UUID, promoted_by: uuid.UUID, now: datetime) -> tuple[ModelRegistry, ModelRegistry]:
        """Atomically promote challenger → champion, current champion → archived.

        Returns (new_champion, archived_former_champion).
        Raises ValueError if challenger not found or no current champion.
        """
        challenger = await self.get_by_id(challenger_id)
        if challenger is None:
            raise ValueError(f"Challenger {challenger_id} not found")
        champion = await self.get_champion()
        if champion is None:
            raise ValueError("No current champion to replace")

        # Archive the former champion
        champion.status = ModelStatus.archived
        # Promote the challenger
        challenger.status = ModelStatus.champion
        challenger.promoted_by = promoted_by
        challenger.promoted_at = now

        await self._session.flush()
        return challenger, champion

    async def update_status(self, model_id: uuid.UUID, status: ModelStatus) -> None:
        await self._session.execute(
            update(ModelRegistry).where(ModelRegistry.id == model_id).values(status=status)
        )
        await self._session.flush()
