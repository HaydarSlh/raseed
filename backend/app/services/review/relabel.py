"""LLM auto-relabel service: Flash-Lite relabels flagged rows as quarantined llm corrections; only owning-user confirmation upgrades to human (constitution Art. III, FR-005/006)."""

from __future__ import annotations

import uuid
from pathlib import Path

import structlog

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.correction import Correction, CorrectionProvenance
from app.infra.llm import get_llm
from app.repositories.corrections_repo import CorrectionsRepository

log = structlog.get_logger(__name__)

_RELABEL_PROMPT_PATH = Path(__file__).parent.parent.parent.parent / "prompts" / "relabel.txt"


def _relabel_prompt(description: str, current_category: str) -> str:
    """Build the mechanical relabel prompt."""
    if _RELABEL_PROMPT_PATH.exists():
        template = _RELABEL_PROMPT_PATH.read_text()
        return template.format(description=description, current_category=current_category)
    # Inline fallback for environments without the prompts/ dir
    return (
        f"Categorize this bank transaction into one of the standard categories.\n"
        f"Transaction: {description}\nCurrent category: {current_category}\n"
        f"Reply with only the category name."
    )


class RelabelService:
    def __init__(self, session: AsyncSession, user_id: uuid.UUID) -> None:
        self._session = session
        self._user_id = user_id
        self._corrections_repo = CorrectionsRepository(session, user_id)

    async def relabel_transaction(
        self,
        transaction_id: uuid.UUID,
        *,
        description: str,
        current_category: str,
    ) -> Correction:
        """Relabel a single transaction via Flash-Lite and quarantine the result.

        The correction is written with provenance=llm, quarantined=True,
        confirmed_by_human=False. The owning user must confirm before it
        becomes training data (FR-006, Art. III).
        """
        llm = get_llm()
        prompt = _relabel_prompt(description, current_category)
        completion = await llm.complete(prompt, tier="mechanical")
        new_category = completion.text.strip().lower().replace(" ", "_")

        correction = Correction(
            user_id=self._user_id,
            transaction_id=transaction_id,
            old_category=current_category,
            new_category=new_category,
            confirmed_by_human=False,
            provenance=CorrectionProvenance.llm,
            quarantined=True,
        )
        result = await self._corrections_repo.write_correction(correction)
        log.info(
            "relabel.queued",
            transaction_id=str(transaction_id),
            new_category=new_category,
            provenance="llm",
        )
        return result

    async def relabel_batch(self, transaction_ids_with_meta: list[tuple[uuid.UUID, str, str]]) -> list[Correction]:
        """Relabel a batch of transactions.

        Args:
            transaction_ids_with_meta: list of (transaction_id, description, current_category)
        """
        results = []
        for transaction_id, description, current_category in transaction_ids_with_meta:
            try:
                correction = await self.relabel_transaction(
                    transaction_id,
                    description=description,
                    current_category=current_category,
                )
                results.append(correction)
            except Exception as exc:
                log.warning("relabel.failed", transaction_id=str(transaction_id), error=str(exc))
        return results
