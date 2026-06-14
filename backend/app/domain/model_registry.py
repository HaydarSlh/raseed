"""ModelRegistry domain model: global table tracking artifacts, hashes, and promotion state (constitution Art. III, DESIGN B)."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import UUID, DateTime, Enum, String, Text, func
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
