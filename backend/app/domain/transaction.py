"""Transaction domain model: provenance/confidence/needs_review structure for the ML lifecycle (constitution Art. III)."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import UUID, Boolean, DateTime, Enum, Float, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.base import Base


class Provenance(enum.StrEnum):
    rule = "rule"
    model = "model"
    llm = "llm"
    human = "human"


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    provenance: Mapped[Provenance] = mapped_column(Enum(Provenance, name="provenance_type"), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    amount: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    merchant: Mapped[str | None] = mapped_column(String(512), nullable=True)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
