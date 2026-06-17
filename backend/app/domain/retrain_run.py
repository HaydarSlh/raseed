"""RetrainRun domain model: global ops table tracking each retrain job (constitution Art. III)."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import UUID, DateTime, Enum, Float, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.base import Base


class TriggerReason(enum.StrEnum):
    correction_count = "correction_count"
    time_cooldown = "time_cooldown"
    manual = "manual"
    drift = "drift"


class RunStatus(enum.StrEnum):
    enqueued = "enqueued"
    running = "running"
    completed = "completed"
    failed = "failed"
    skipped = "skipped"  # too few eligible labels


class RetrainRun(Base):
    __tablename__ = "retrain_runs"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_retrain_runs_idempotency_key"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trigger_reason: Mapped[TriggerReason] = mapped_column(Enum(TriggerReason, name="trigger_reason_type"), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(256), nullable=False, unique=True)
    status: Mapped[RunStatus] = mapped_column(Enum(RunStatus, name="run_status_type"), nullable=False, default=RunStatus.enqueued)
    skipped_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # FK to model_registry set after challenger is created; null if skipped/failed
    challenger_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    champion_macro_f1: Mapped[float | None] = mapped_column(Float, nullable=True)
    challenger_macro_f1: Mapped[float | None] = mapped_column(Float, nullable=True)
    gate_verdict: Mapped[str | None] = mapped_column(String(32), nullable=True)  # 'beats' | 'does_not_beat'
    labels_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
