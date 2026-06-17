"""Gate service: read and expose the stored champion/challenger verdict from retrain_runs and model_registry.

The heavy gate scoring (sklearn/holdout/onnxruntime) runs IN the trainer process (T037).
This backend service only reads the persisted verdict — no sklearn or holdout loading here
(keeps the lean backend image lean, constitution Art. III, R9/C1).
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

import structlog

from app.repositories.model_registry_repo import ModelRegistryRepository
from app.repositories.retrain_runs_repo import RetrainRunsRepository

log = structlog.get_logger(__name__)


class GateService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._runs_repo = RetrainRunsRepository(session)
        self._registry_repo = ModelRegistryRepository(session)

    async def get_verdict(self, retrain_run_id: uuid.UUID) -> dict:
        """Return the stored gate verdict for a retrain run."""
        run = await self._runs_repo.get_by_id(retrain_run_id)
        if run is None:
            return {"verdict": None, "error": "run not found"}
        return {
            "verdict": run.gate_verdict,
            "champion_macro_f1": run.champion_macro_f1,
            "challenger_macro_f1": run.challenger_macro_f1,
            "labels_used": run.labels_used,
        }

    async def challenger_beats_champion(self, model_registry_id: uuid.UUID) -> bool:
        """Check if a challenger in the registry has gate_verdict='beats'.

        The verdict is stored in the retrain_run linked to the challenger registry row.
        """
        challenger = await self._registry_repo.get_by_id(model_registry_id)
        if challenger is None or challenger.retrain_run_id is None:
            return False
        run = await self._runs_repo.get_by_id(challenger.retrain_run_id)
        if run is None:
            return False
        return run.gate_verdict == "beats"
