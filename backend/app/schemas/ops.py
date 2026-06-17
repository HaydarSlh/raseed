"""Ops request/response schemas: retrain, promote, model listing, drift+retrain history (contracts/http-api.md)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


# Retrain
class RetrainRequest(BaseModel):
    force: bool = False


class RetrainResponse(BaseModel):
    retrain_run_id: uuid.UUID
    status: str


# Promote
class PromoteRequest(BaseModel):
    model_registry_id: uuid.UUID


class PromoteResponse(BaseModel):
    promoted: uuid.UUID
    archived: uuid.UUID
    model_server_reloaded: bool


# Model registry
class ModelSummary(BaseModel):
    id: uuid.UUID
    version: str
    sha256: str
    metrics: dict | None = None
    gate_verdict: str | None = None


class ModelsResponse(BaseModel):
    champion: ModelSummary | None
    promotable: list[ModelSummary]


# Drift
class DriftStatus(BaseModel):
    evaluated_at: datetime | None = None
    mean_confidence: float | None = None
    correction_rate: float | None = None
    psi: float | None = None
    new_merchant_rate: float | None = None
    fired: bool = False
    fired_signals: list[str] = []
    triggered_retrain: bool = False


class DriftSeriesPoint(BaseModel):
    evaluated_at: datetime
    mean_confidence: float
    correction_rate: float


class DriftResponse(BaseModel):
    current: DriftStatus
    thresholds: dict
    series: list[DriftSeriesPoint]


# Retrain history
class RetrainHistoryItem(BaseModel):
    id: uuid.UUID
    trigger_reason: str
    status: str
    champion_macro_f1: float | None = None
    challenger_macro_f1: float | None = None
    gate_verdict: str | None = None
    labels_used: int | None = None
    challenger_id: uuid.UUID | None = None
    created_at: datetime
    completed_at: datetime | None = None


class RetrainsResponse(BaseModel):
    runs: list[RetrainHistoryItem]
