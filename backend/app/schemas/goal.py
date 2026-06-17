"""Goal REST schemas (Phase 4 — GET/POST/PATCH /goals contract)."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.domain.goal import GoalStatus


class GoalCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)
    target_amount: float = Field(..., gt=0)
    target_date: date


class GoalUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=256)
    target_amount: float | None = Field(None, gt=0)
    target_date: date | None = None
    status: GoalStatus | None = None


class GoalOut(BaseModel):
    id: uuid.UUID
    name: str
    target_amount: float
    target_date: date
    status: GoalStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
