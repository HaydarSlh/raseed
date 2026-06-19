"""Review queue service: list needs_review + quarantined rows; confirm corrections (constitution Art. III — human provenance path)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.correction import Correction, CorrectionProvenance
from app.domain.transaction import Transaction
from app.domain.user_settings import ReviewMode, UserSettings
from app.repositories.corrections_repo import CorrectionsRepository
from app.schemas.review import ConfirmResponse, ReviewItem, ReviewQueueResponse

log = structlog.get_logger(__name__)


class ReviewQueueService:
    def __init__(self, session: AsyncSession, user_id: uuid.UUID) -> None:
        self._session = session
        self._user_id = user_id
        self._corrections_repo = CorrectionsRepository(session, user_id)

    async def _get_review_mode(self) -> str:
        result = await self._session.execute(
            select(UserSettings).where(UserSettings.user_id == self._user_id)
        )
        settings = result.scalar_one_or_none()
        if settings is None:
            return ReviewMode.manual.value
        return settings.review_mode.value

    async def list_queue(self) -> ReviewQueueResponse:
        """Return the user's needs_review transactions + quarantined LLM relabels."""
        # needs_review transactions (RLS-scoped via session variable)
        result = await self._session.execute(
            select(Transaction)
            .where(Transaction.user_id == self._user_id)
            .where(Transaction.needs_review == True)  # noqa: E712
            .order_by(Transaction.occurred_at.desc())
        )
        txns: list[Transaction] = list(result.scalars().all())

        # Quarantined LLM relabels awaiting owning-user confirmation
        quarantined = await self._corrections_repo.list_quarantined()
        quarantined_txn_ids = {c.transaction_id for c in quarantined if c.transaction_id}

        items: list[ReviewItem] = []
        for txn in txns:
            is_quarantined = txn.id in quarantined_txn_ids
            items.append(
                ReviewItem(
                    transaction_id=txn.id,
                    description=getattr(txn, "normalized_description", None),
                    merchant=getattr(txn, "merchant", None),
                    amount=float(txn.amount) if txn.amount is not None else None,
                    occurred_at=txn.occurred_at,
                    current_category=txn.category or "",
                    confidence=txn.confidence,
                    provenance=txn.provenance.value if txn.provenance else "model",
                    quarantined=is_quarantined,
                )
            )

        review_mode = await self._get_review_mode()
        return ReviewQueueResponse(items=items, review_mode=review_mode)

    async def confirm(self, transaction_id: uuid.UUID, category: str) -> ConfirmResponse:
        """Confirm or correct a flagged transaction's category (human provenance)."""
        # Load the transaction
        result = await self._session.execute(
            select(Transaction)
            .where(Transaction.id == transaction_id)
            .where(Transaction.user_id == self._user_id)
        )
        txn = result.scalar_one_or_none()
        if txn is None:
            from app.core.exceptions import NotFoundError
            raise NotFoundError(f"Transaction {transaction_id} not found")

        now = datetime.now(UTC)

        # Check if there's a quarantined LLM correction for this transaction
        existing = await self._corrections_repo.get_by_transaction(transaction_id)
        if existing is not None and existing.quarantined:
            # Upgrade quarantined LLM relabel to human-confirmed
            correction = await self._corrections_repo.confirm_correction(
                existing.id, category, now
            )
        else:
            # Fresh human correction
            correction = Correction(
                user_id=self._user_id,
                transaction_id=transaction_id,
                old_category=txn.category,
                new_category=category,
                confirmed_by_human=True,
                provenance=CorrectionProvenance.human,
                quarantined=False,
                confirmed_at=now,
            )
            await self._corrections_repo.write_correction(correction)

        # Update the transaction
        txn.category = category
        txn.provenance = "human"  # type: ignore[assignment]
        txn.needs_review = False
        await self._session.flush()

        log.info("review.confirm", transaction_id=str(transaction_id), category=category)
        return ConfirmResponse(
            transaction_id=transaction_id,
            category=category,
            provenance="human",
            needs_review=False,
        )
