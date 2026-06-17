"""Chat request/response schemas (Phase 4 — POST /chat streaming contract)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4096)
    session_id: str = Field(..., min_length=1, max_length=128)


class DeltaEvent(BaseModel):
    delta: str


class Citation(BaseModel):
    document_slug: str
    heading_path: str


class FinalEvent(BaseModel):
    done: bool = True
    route: str  # "deterministic" | "agent"
    citations: list[Citation] = Field(default_factory=list)
    bounded: bool = False


class RouterDecision(BaseModel):
    route: str  # "deterministic" | "agent"
    answer: str | None = None  # filled when route == "deterministic"
