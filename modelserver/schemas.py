"""Request/response schemas for the model-server API."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class CategoryScore(BaseModel):
    category: str
    score: float = Field(ge=0.0, le=1.0)


class PredictRequest(BaseModel):
    description: str = Field(min_length=1, max_length=512)
    top_k: int = Field(default=3, ge=1, le=5)

    @field_validator("description", mode="before")
    @classmethod
    def strip_and_check(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("description must not be whitespace-only")
        return stripped


class PredictResponse(BaseModel):
    category: str
    confidence: float = Field(ge=0.0, le=1.0)
    # Descending by score; primary category is included at rank 0.
    alternatives: list[CategoryScore]
    low_confidence: bool
