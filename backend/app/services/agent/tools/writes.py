"""Write tools: add_transaction, reclassify_transaction (FR-020/021, Art. III, contracts/tools)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.transactions_repo import TransactionsRepository
from app.services.agent.ratelimit import check_write_rate
from app.services.agent.tools.registry import register_tool


class AddTransactionInput(BaseModel):
    txn_date: date
    amount: float
    description: str = Field(..., min_length=1, max_length=1024)
    merchant: str | None = None
    currency: str = "GBP"
    _session: object | None = None
    _user_id: uuid.UUID | None = None

    model_config = {"arbitrary_types_allowed": True}


class ReclassifyTransactionInput(BaseModel):
    transaction_id: uuid.UUID
    new_category: str = Field(..., min_length=1, max_length=128)
    _session: object | None = None
    _user_id: uuid.UUID | None = None

    model_config = {"arbitrary_types_allowed": True}


async def add_transaction(
    txn_date: date,
    amount: float,
    description: str,
    merchant: str | None = None,
    currency: str = "GBP",
    _session: AsyncSession | None = None,
    _user_id: uuid.UUID | None = None,
) -> dict:
    """Add a transaction via the Phase-3 ingestion service (rate-limited, RLS-scoped)."""
    if _session is None or _user_id is None:
        return {"error": "Session context not available"}

    from app.core.config import get_settings
    from app.infra.modelserver_client import ModelServerClient
    from app.schemas.ingestion import ParsedRow
    from app.services.ingestion import ingest_transactions

    settings = get_settings()
    await check_write_rate(_user_id, limit=settings.write_rate_per_min)

    row = ParsedRow(
        amount=Decimal(str(amount)),
        description=description,
        merchant=merchant,
        currency=currency,
        occurred_at=datetime.combine(txn_date, datetime.min.time()),
    )
    repo = TransactionsRepository(_session, _user_id)
    model_client = ModelServerClient()
    result = await ingest_transactions(_user_id, [row], repo, model_client)

    return {
        "id": None,  # dedup-insert doesn't return ID easily; use None
        "category": None,
        "confidence": None,
        "provenance": "model",
        "needs_review": result.needs_review > 0,
    }


async def reclassify_transaction(
    transaction_id: uuid.UUID,
    new_category: str,
    _session: AsyncSession | None = None,
    _user_id: uuid.UUID | None = None,
) -> dict:
    """Record a human-confirmed reclassification (Art. III, FR-021). Rate-limited."""
    if _session is None or _user_id is None:
        return {"error": "Session context not available"}

    from app.core.config import get_settings
    from app.domain.correction import Correction
    from app.domain.transaction import Provenance

    settings = get_settings()
    await check_write_rate(_user_id, limit=settings.write_rate_per_min)

    repo = TransactionsRepository(_session, _user_id)
    txn = await repo.get_by_id(transaction_id)
    if txn is None:
        return {"error": "Transaction not found or not yours"}

    # Write a human-confirmed correction (Art. III — only human-confirmed labels can train)
    correction = Correction(
        transaction_id=transaction_id,
        user_id=_user_id,
        old_category=txn.category,
        new_category=new_category,
        confirmed_by_human=True,
    )
    _session.add(correction)

    # Update the transaction's category and provenance
    txn.category = new_category
    txn.provenance = Provenance.human
    txn.needs_review = False
    await _session.flush()

    return {"transaction_id": str(transaction_id), "new_category": new_category, "provenance": "human"}


register_tool("add_transaction", AddTransactionInput, add_transaction)
register_tool("reclassify_transaction", ReclassifyTransactionInput, reclassify_transaction)
