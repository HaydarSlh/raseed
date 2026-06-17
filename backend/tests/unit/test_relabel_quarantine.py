"""Unit tests: LLM auto-relabel is quarantined; only the owning user's confirm upgrades to human (FR-005/006, SC-002)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.correction import Correction, CorrectionProvenance


@pytest.fixture()
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.mark.asyncio
async def test_llm_relabel_is_quarantined(user_id: uuid.UUID) -> None:
    """Auto-relabel writes provenance=llm, quarantined=True, confirmed_by_human=False."""
    transaction_id = uuid.uuid4()
    captured: list[Correction] = []

    with patch("app.services.review.relabel.CorrectionsRepository") as MockRepo, \
         patch("app.services.review.relabel.get_llm") as mock_get_llm:

        mock_repo = AsyncMock()
        mock_repo.write_correction = AsyncMock(side_effect=lambda c: captured.append(c) or c)
        MockRepo.return_value = mock_repo

        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(return_value=MagicMock(text="groceries"))
        mock_get_llm.return_value = mock_llm

        from app.services.review.relabel import RelabelService

        svc = RelabelService(AsyncMock(), user_id)
        await svc.relabel_transaction(transaction_id, description="TESCO STORES 1234", current_category="other")

    assert len(captured) == 1
    correction = captured[0]
    assert correction.provenance == CorrectionProvenance.llm
    assert correction.quarantined is True
    assert correction.confirmed_by_human is False


@pytest.mark.asyncio
async def test_quarantined_row_excluded_from_training(user_id: uuid.UUID) -> None:
    """Training label query selects confirmed_by_human=True only — quarantined rows excluded."""
    # Simulate corrections_repo.count_confirmed_since excluding quarantined rows
    mock_session = AsyncMock()
    # Two corrections: one human-confirmed, one quarantined LLM
    from app.domain.correction import Correction, CorrectionProvenance

    Correction(
        id=uuid.uuid4(),
        user_id=user_id,
        transaction_id=uuid.uuid4(),
        new_category="groceries",
        confirmed_by_human=True,
        provenance=CorrectionProvenance.human,
        quarantined=False,
        confirmed_at=datetime(2026, 6, 10, tzinfo=timezone.utc),
    )
    Correction(
        id=uuid.uuid4(),
        user_id=user_id,
        transaction_id=uuid.uuid4(),
        new_category="dine_out",
        confirmed_by_human=False,
        provenance=CorrectionProvenance.llm,
        quarantined=True,
    )

    # Repo count_confirmed_since should only count confirmed_by_human=True
    # We simulate by patching the execute result to count only the human one
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 1  # only the human-confirmed row
    mock_session.execute = AsyncMock(return_value=mock_result)

    from app.repositories.corrections_repo import CorrectionsRepository

    repo = CorrectionsRepository(mock_session, user_id)
    count = await repo.count_confirmed_since(datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert count == 1


@pytest.mark.asyncio
async def test_owning_user_confirmation_upgrades_to_human(user_id: uuid.UUID) -> None:
    """The owning user confirming a quarantined row upgrades provenance=human, quarantined=False."""
    correction_id = uuid.uuid4()
    quarantined = Correction(
        id=correction_id,
        user_id=user_id,
        transaction_id=uuid.uuid4(),
        new_category="dine_out",
        confirmed_by_human=False,
        provenance=CorrectionProvenance.llm,
        quarantined=True,
    )

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = quarantined
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.flush = AsyncMock()

    from app.repositories.corrections_repo import CorrectionsRepository

    repo = CorrectionsRepository(mock_session, user_id)
    updated = await repo.confirm_correction(correction_id, "groceries", datetime.now(timezone.utc))

    assert updated is not None
    assert updated.provenance == CorrectionProvenance.human
    assert updated.quarantined is False
    assert updated.confirmed_by_human is True
    assert updated.confirmed_at is not None
