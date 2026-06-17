"""ModelRegistry domain model: global table tracking artifacts, hashes, and promotion state (constitution Art. III, DESIGN B)."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import UUID, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.base import Base


class ModelStatus(enum.StrEnum):
    challenger = "challenger"
    champion = "champion"
    archived = "archived"


class ModelRegistry(Base):
    __tablename__ = "model_registry"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    sha256: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ModelStatus] = mapped_column(Enum(ModelStatus, name="model_status_type"), nullable=False, default=ModelStatus.challenger)
    model_card: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Phase 5 additions
    artifact_uri: Mapped[str | None] = mapped_column(Text, nullable=True)  # MinIO key categorizer/<sha256>/…
    metrics: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # macro_f1, per_class_f1, latency_ms
    retrain_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("retrain_runs.id", ondelete="SET NULL"), nullable=True)
    promoted_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    promoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
