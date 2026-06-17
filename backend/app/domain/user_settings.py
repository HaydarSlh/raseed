"""UserSettings domain model: per-user review-mode preference (constitution Art. II — RLS-scoped)."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import UUID, DateTime, Enum, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.base import Base


class ReviewMode(enum.StrEnum):
    manual = "manual"
    auto_relabel = "auto_relabel"


class UserSettings(Base):
    __tablename__ = "user_settings"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    review_mode: Mapped[ReviewMode] = mapped_column(Enum(ReviewMode, name="review_mode_type"), nullable=False, default=ReviewMode.manual)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
