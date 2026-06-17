"""ErasureAudit: operator-only audit record produced by every right-to-erasure request (Phase 6, FR-009)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, UUID, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.base import Base


class ErasureAudit(Base):
    """Append-only record of every erasure operation.

    NOT subject to user-scoped RLS — readable by operators only and
    NOT purged when the referenced user is erased (retained for compliance).
    """

    __tablename__ = "erasure_audit"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    per_store_counts: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
