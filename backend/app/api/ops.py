"""Operator-only ops API: POST /ops/retrain, POST /ops/promote, GET /ops/models, GET /ops/drift, GET /ops/retrains (constitution Art. II/III, FR-015/016/019)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_active_user
from app.core.exceptions import PermissionError as RaseedPermissionError
from app.core.exceptions import UpstreamError
from app.domain.user import User
from app.infra.db import get_session_factory
from app.repositories.drift_repo import DriftRepository
from app.repositories.model_registry_repo import ModelRegistryRepository
from app.repositories.retrain_runs_repo import RetrainRunsRepository
from app.schemas.ops import (
    DriftResponse,
    DriftSeriesPoint,
    DriftStatus,
    ModelsResponse,
    ModelSummary,
    PromoteRequest,
    PromoteResponse,
    RetrainHistoryItem,
    RetrainRequest,
    RetrainResponse,
    RetrainsResponse,
)
from app.services.lifecycle.promote import PromoteService
from app.services.lifecycle.trigger import RetrainTriggerService

router = APIRouter(prefix="/ops", tags=["ops"])


def _require_operator(user: User = Depends(current_active_user)) -> User:  # noqa: B008
    """FastAPI dependency: raises 403 if the user is not an operator (FR-016)."""
    if not user.is_operator:
        raise HTTPException(status_code=403, detail="Operator access required.")
    return user


async def _get_plain_session():  # noqa: ANN201
    """Plain session without RLS for ops queries (global ops tables, no user scope)."""
    factory = get_session_factory()
    async with factory() as session:
        yield session


@router.post("/retrain", response_model=RetrainResponse, status_code=202)
async def trigger_retrain(
    body: RetrainRequest,
    operator: User = Depends(_require_operator),  # noqa: B008
    session: AsyncSession = Depends(_get_plain_session),  # noqa: B008
) -> RetrainResponse:
    """Manually enqueue a retrain (operator-only). force=True overrides the cooldown."""
    svc = RetrainTriggerService(session)
    run, enqueued = await svc.trigger_manual(force=body.force)
    if run is None:
        raise HTTPException(status_code=409, detail="retrain cooldown active; pass force=true to override")
    if not enqueued and not body.force:
        raise HTTPException(status_code=409, detail="retrain cooldown active; pass force=true to override")
    return RetrainResponse(retrain_run_id=run.id, status=run.status.value)


@router.post("/promote", response_model=PromoteResponse)
async def promote_model(
    body: PromoteRequest,
    operator: User = Depends(_require_operator),  # noqa: B008
    session: AsyncSession = Depends(_get_plain_session),  # noqa: B008
) -> PromoteResponse:
    """Promote a challenger to champion (operator HIL, beats-champion required)."""
    svc = PromoteService(session)
    try:
        return await svc.promote(body.model_registry_id, uuid.UUID(str(operator.id)))
    except RaseedPermissionError as exc:
        raise HTTPException(status_code=409, detail=exc.message) from exc
    except UpstreamError as exc:
        raise HTTPException(status_code=502, detail=exc.message) from exc


@router.get("/models", response_model=ModelsResponse)
async def list_models(
    operator: User = Depends(_require_operator),  # noqa: B008
    session: AsyncSession = Depends(_get_plain_session),  # noqa: B008
) -> ModelsResponse:
    """List current champion and promotable challengers."""
    registry_repo = ModelRegistryRepository(session)
    runs_repo = RetrainRunsRepository(session)

    champion = await registry_repo.get_champion()
    promotable_entries = await registry_repo.list_promotable()

    champion_summary: ModelSummary | None = None
    if champion is not None:
        champion_summary = ModelSummary(
            id=champion.id,
            version=champion.version,
            sha256=champion.sha256,
            metrics=champion.metrics,
        )

    promotable: list[ModelSummary] = []
    for entry in promotable_entries:
        verdict: str | None = None
        if entry.retrain_run_id:
            run = await runs_repo.get_by_id(entry.retrain_run_id)
            verdict = run.gate_verdict if run else None
        # Only surface challengers that beat the champion
        if verdict == "beats":
            promotable.append(ModelSummary(
                id=entry.id,
                version=entry.version,
                sha256=entry.sha256,
                metrics=entry.metrics,
                gate_verdict=verdict,
            ))

    return ModelsResponse(champion=champion_summary, promotable=promotable)


# ── Read endpoints for US4 (ops dashboard) — added in T050 ───────────────────

@router.get("/drift", response_model=DriftResponse)
async def get_drift(
    operator: User = Depends(_require_operator),  # noqa: B008
    session: AsyncSession = Depends(_get_plain_session),  # noqa: B008
) -> DriftResponse:
    """Current drift status + series for charts, with thresholds."""
    from app.core.config import get_settings
    settings = get_settings()

    drift_repo = DriftRepository(session)
    latest = await drift_repo.get_latest()
    series_rows = await drift_repo.list_series(limit=30)

    thresholds = {
        "mean_confidence_min": settings.drift_mean_confidence_min,
        "correction_rate_max": settings.drift_correction_rate_max,
        "psi_max": settings.drift_psi_max,
        "new_merchant_rate_max": settings.drift_new_merchant_rate_max,
    }

    current = DriftStatus()
    if latest is not None:
        current = DriftStatus(
            evaluated_at=latest.evaluated_at,
            mean_confidence=latest.mean_confidence,
            correction_rate=latest.correction_rate,
            psi=latest.psi,
            new_merchant_rate=latest.new_merchant_rate,
            fired=latest.fired,
            fired_signals=latest.fired_signals or [],
            triggered_retrain=latest.triggered_retrain,
        )

    series = [
        DriftSeriesPoint(
            evaluated_at=row.evaluated_at,
            mean_confidence=row.mean_confidence,
            correction_rate=row.correction_rate,
        )
        for row in series_rows
    ]

    return DriftResponse(current=current, thresholds=thresholds, series=series)


@router.get("/retrains", response_model=RetrainsResponse)
async def get_retrains(
    operator: User = Depends(_require_operator),  # noqa: B008
    session: AsyncSession = Depends(_get_plain_session),  # noqa: B008
) -> RetrainsResponse:
    """Retrain history with champion-vs-challenger numbers."""
    runs_repo = RetrainRunsRepository(session)
    runs = await runs_repo.list_history(limit=20)
    return RetrainsResponse(
        runs=[
            RetrainHistoryItem(
                id=r.id,
                trigger_reason=r.trigger_reason.value,
                status=r.status.value,
                champion_macro_f1=r.champion_macro_f1,
                challenger_macro_f1=r.challenger_macro_f1,
                gate_verdict=r.gate_verdict,
                labels_used=r.labels_used,
                challenger_id=r.challenger_id,
                created_at=r.created_at,
                completed_at=r.completed_at,
            )
            for r in runs
        ]
    )
