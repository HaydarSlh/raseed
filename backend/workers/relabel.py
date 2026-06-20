"""Batch LLM relabel worker: re-categorizes a user's flagged rows via Flash-Lite.

Triggered via the RQ 'default' queue by the review page's "LLM label all" button
and by switching review_mode to auto_relabel. Results are written as quarantined
llm-provenance corrections that still require the owning user's confirmation before
they count as training data (constitution Art. III, FR-005/006).
"""

from __future__ import annotations

import asyncio
import uuid

from sqlalchemy import select

from app.core.config import get_settings
from app.domain.transaction import Transaction
from app.domain.user import (
    User,  # noqa: F401 — registers User table in mapper so FK to users resolves
)
from app.infra.db import get_async_sessionmaker, init_engine
from app.infra.llm import build_llm, init_llm
from app.services.review.relabel import RelabelService


async def _run_async(user_id: uuid.UUID) -> None:
    settings = get_settings()
    engine = init_engine(settings.database_url)
    # The worker process is separate from FastAPI — initialise the LLM adapter
    # here so RelabelService.relabel_transaction can call get_llm() without
    # hitting the "not initialised" assertion.
    llm = build_llm(
        gemini_api_key=settings.gemini_api_key,
        grok_api_key=settings.grok_api_key,
        use_fake=settings.use_fake_llm,
    )
    init_llm(llm)
    try:
        factory = get_async_sessionmaker()
        async with factory() as session:
            result = await session.execute(
                select(Transaction)
                .where(Transaction.user_id == user_id)
                .where(Transaction.needs_review == True)  # noqa: E712
            )
            txns = list(result.scalars().all())
            svc = RelabelService(session, user_id)
            batch = [
                (t.id, t.normalized_description or "", t.category or "other")
                for t in txns
                if t.normalized_description
            ]
            if batch:
                await svc.relabel_batch(batch)
                await session.commit()
    finally:
        await engine.dispose()


def run_batch_relabel(user_id: str) -> None:
    """RQ entry point: called by the light worker with user_id as a string."""
    asyncio.run(_run_async(uuid.UUID(user_id)))
