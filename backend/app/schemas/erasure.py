"""Pydantic schemas for the right-to-erasure endpoint (Phase 6, FR-008/FR-009)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel


class ErasureResponse(BaseModel):
    audit_id: uuid.UUID
    status: str
    deleted_counts: dict[str, int]
    message: str
