"""Ingestion API: POST /uploads (file) and POST /transactions (manual form).

Both paths converge on the shared ingest_transactions() service — the only difference
is how ParsedRow instances are produced (constitution R1). Thin routers: no SQL,
no business logic (constitution Art. I layering).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_active_user
from app.domain.transaction import Transaction
from app.domain.user import User
from app.infra.db import get_session_factory
from app.infra.modelserver_client import ModelServerClient, get_modelserver_client
from app.repositories.transactions_repo import TransactionsRepository
from app.schemas.ingestion import ParsedRow
from app.services.ingestion import ingest_transactions
from app.services.parsing import parse_statement

router = APIRouter(tags=["ingestion"])

_MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


# ─── Shared session dep with RLS ──────────────────────────────────────────────

async def _rls_session(
    user: User = Depends(current_active_user),
) -> AsyncSession:  # type: ignore[misc]
    """Yield an AsyncSession with app.user_id set (RLS armed)."""
    factory = get_session_factory()
    async with factory() as session:
        await session.execute(
            __import__("sqlalchemy", fromlist=["text"]).text(
                "SELECT set_config('app.user_id', :uid, true)"
            ),
            {"uid": str(user.id)},
        )
        yield session


# ─── POST /uploads ────────────────────────────────────────────────────────────

class UploadResponse(BaseModel):
    ingested: int
    needs_review: int
    duplicates_skipped: int
    recompute_enqueued: bool


@router.post("/uploads", response_model=UploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_statement(
    file: UploadFile,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(_rls_session),
    model_client: ModelServerClient = Depends(get_modelserver_client),
) -> UploadResponse:
    """Parse a CSV-class statement in-memory, classify, dedup, and store.

    Raw bytes are never persisted (constitution Art. II). Returns 202 because
    the recompute job is async — dashboard data updates within worker latency.
    """
    content = await file.read()
    if len(content) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File too large (max 10 MB).")
    if not content:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Empty file.")

    try:
        rows = parse_statement(content, filename=file.filename or "")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    if not rows:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No parseable rows found in file.")

    repo = TransactionsRepository(session, user.id)
    async with model_client:
        result = await ingest_transactions(user.id, rows, repo, model_client)
    await session.commit()

    return UploadResponse(
        ingested=result.ingested,
        needs_review=result.needs_review,
        duplicates_skipped=result.duplicates_skipped,
        recompute_enqueued=result.ingested > 0,
    )


# ─── POST /transactions ───────────────────────────────────────────────────────

class ManualTransactionRequest(BaseModel):
    txn_date: datetime
    amount: Decimal = Field(..., ne=Decimal("0"))
    description: str = Field(..., min_length=1, max_length=1024)
    merchant: str | None = None
    currency: str = "GBP"


class ManualTransactionResponse(BaseModel):
    id: uuid.UUID
    category: str | None
    confidence: float | None
    provenance: str
    needs_review: bool


@router.post("/transactions", response_model=ManualTransactionResponse, status_code=status.HTTP_201_CREATED)
async def add_transaction(
    body: ManualTransactionRequest,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(_rls_session),
    model_client: ModelServerClient = Depends(get_modelserver_client),
) -> ManualTransactionResponse:
    """Add a single transaction entered manually (same pipeline as upload)."""
    row = ParsedRow(
        occurred_at=body.txn_date,
        amount=body.amount,
        description=body.description,
        merchant=body.merchant,
        currency=body.currency,
    )
    repo = TransactionsRepository(session, user.id)
    async with model_client:
        await ingest_transactions(user.id, [row], repo, model_client)
    await session.commit()

    # Retrieve the newly inserted transaction to return its fields.
    from sqlalchemy import select
    stmt = (
        select(Transaction)
        .where(Transaction.user_id == user.id)
        .order_by(Transaction.created_at.desc())
        .limit(1)
    )
    txn_result = await session.execute(stmt)
    txn = txn_result.scalar_one_or_none()
    if txn is None:
        # Row was a duplicate — return a placeholder indicating as much.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Transaction matches an existing entry (duplicate).",
        )

    return ManualTransactionResponse(
        id=txn.id,
        category=txn.category,
        confidence=txn.confidence,
        provenance=txn.provenance.value,
        needs_review=txn.needs_review,
    )
