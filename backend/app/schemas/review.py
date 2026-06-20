"""Review queue and settings request/response schemas (contracts/http-api.md)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class ReviewItem(BaseModel):
    transaction_id: uuid.UUID
    description: str | None = None
    merchant: str | None = None
    amount: float | None = None
    occurred_at: datetime | None = None
    current_category: str
    confidence: float | None = None
    provenance: str
    quarantined: bool = False


class ReviewQueueResponse(BaseModel):
    items: list[ReviewItem]
    review_mode: str


class ConfirmRequest(BaseModel):
    transaction_id: uuid.UUID
    category: str


class ConfirmResponse(BaseModel):
    transaction_id: uuid.UUID
    category: str
    provenance: str
    needs_review: bool


class ReviewModeResponse(BaseModel):
    review_mode: str


class ReviewModeRequest(BaseModel):
    review_mode: str


class RelabelAllResponse(BaseModel):
    queued: bool
    user_id: uuid.UUID
