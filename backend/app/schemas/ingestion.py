"""Ingestion DTOs (Pydantic): the parsed-and-scrubbed row that enters the shared ingestion
function, and the result it returns. Pure data — no DB or HTTP concerns (constitution Art. I)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class ParsedRow(BaseModel):
    """One transaction parsed from a statement or the manual form, already PAN/IBAN-scrubbed."""

    occurred_at: datetime
    amount: Decimal
    description: str
    merchant: str | None = None
    currency: str | None = "GBP"


class IngestResult(BaseModel):
    ingested: int = 0
    needs_review: int = 0
    duplicates_skipped: int = 0
