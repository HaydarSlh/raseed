"""DriftSignal domain model: per-evaluation snapshot of drift metrics (constitution Art. III/V)."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import UUID, Boolean, DateTime, Enum, Float, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.base import Base


class DriftSource(enum.StrEnum):
    scheduled = "scheduled"
    on_demand = "on_demand"
    simulation = "simulation"


class DriftSignal(Base):
    __tablename__ = "drift_signals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    # Primary signals
    mean_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    correction_rate: Mapped[float] = mapped_column(Float, nullable=False)
    # Secondary signals
    psi: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    new_merchant_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # Thresholds in effect at evaluation (for chart threshold lines)
    thresholds: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Outcome
    fired: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    fired_signals: Mapped[list | None] = mapped_column(JSONB, nullable=True)  # list of crossed signal names
    triggered_retrain: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source: Mapped[DriftSource] = mapped_column(Enum(DriftSource, name="drift_source_type"), nullable=False, default=DriftSource.scheduled)
