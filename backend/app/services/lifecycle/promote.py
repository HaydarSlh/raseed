"""Operator promotion service: verify gate_verdict='beats', registry swap, model-server /reload; rollback on reload failure (constitution Art. III, FR-015/017)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PermissionError, UpstreamError
from app.infra.modelserver_client import ModelServerClient
from app.repositories.model_registry_repo import ModelRegistryRepository
from app.repositories.retrain_runs_repo import RetrainRunsRepository
from app.schemas.ops import PromoteResponse
from app.services.lifecycle.gate import GateService

log = structlog.get_logger(__name__)


class PromoteService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._registry_repo = ModelRegistryRepository(session)
        self._runs_repo = RetrainRunsRepository(session)
        self._gate_svc = GateService(session)

    async def promote(self, model_registry_id: uuid.UUID, operator_user_id: uuid.UUID) -> PromoteResponse:
        """Promote a challenger to champion.

        Raises:
            PermissionError: gate_verdict != 'beats' (FR-015).
            UpstreamError: model-server reload failed (SHA mismatch or timeout).
        """
        # 1. Gate check — challenger must have beaten the champion
        if not await self._gate_svc.challenger_beats_champion(model_registry_id):
            raise PermissionError("Challenger has not beaten the champion; promotion denied (FR-015).")

        challenger = await self._registry_repo.get_by_id(model_registry_id)
        if challenger is None:
            from app.core.exceptions import NotFoundError
            raise NotFoundError(f"Model {model_registry_id} not found")

        sha256 = challenger.sha256

        # 2. Registry swap (champion → archived, challenger → champion) — in one flush
        new_champion, archived = await self._registry_repo.promote(
            model_registry_id, operator_user_id, datetime.now(UTC)
        )

        # 3. Model-server /reload with the authoritative SHA from this backend (C2/R3)
        async with ModelServerClient() as client:
            try:
                await client.reload(sha256)
            except Exception as exc:
                # Roll back the registry swap on reload failure (FR-017)
                await self._session.rollback()
                log.error("promote.reload_failed", sha256=sha256, error=str(exc))
                raise UpstreamError(
                    f"model-server reload failed (hash mismatch); champion unchanged: {exc}"
                ) from exc

        await self._session.commit()
        log.info(
            "promote.success",
            new_champion=str(new_champion.id),
            archived=str(archived.id),
            sha256=sha256,
        )
        return PromoteResponse(
            promoted=new_champion.id,
            archived=archived.id,
            model_server_reloaded=True,
        )
