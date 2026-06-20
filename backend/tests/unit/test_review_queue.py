"""Unit tests: review queue — confirming a row writes a human-provenance correction and clears needs_review; queue is RLS-scoped to the owner (FR-001/003/007)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.correction import Correction, CorrectionProvenance
from app.domain.transaction import Transaction


def _make_txn(user_id: uuid.UUID, *, needs_review: bool = True) -> Transaction:
    txn = Transaction(
        id=uuid.uuid4(),
        user_id=user_id,
        amount=-42.10,
        currency="GBP",
        occurred_at=datetime(2026, 6, 10, tzinfo=UTC),
        merchant="TESCO",
        normalized_description="TESCO STORES 1234",
        category="groceries",
        confidence=0.61,
        provenance="model",
        needs_review=needs_review,
    )
    return txn


@pytest.fixture()
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.mark.asyncio
async def test_confirm_writes_human_correction(user_id: uuid.UUID) -> None:
    """Confirming a needs_review row writes a correction with provenance=human, confirmed_by_human=True."""
    txn = _make_txn(user_id)
    captured: list[Correction] = []

    mock_session = AsyncMock()
    mock_session.add = MagicMock(side_effect=lambda obj: captured.append(obj))
    mock_session.flush = AsyncMock()
    mock_session.execute = AsyncMock()

    # Simulate transaction lookup returning our txn
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = txn
    mock_session.execute.return_value = mock_result

    with patch("app.services.review.queue.CorrectionsRepository") as MockRepo:
        mock_repo = AsyncMock()
        mock_repo.get_by_transaction = AsyncMock(return_value=None)  # no existing correction
        mock_repo.write_correction = AsyncMock(side_effect=lambda c: c)
        MockRepo.return_value = mock_repo

        from app.services.review.queue import ReviewQueueService

        svc = ReviewQueueService(mock_session, user_id)
        await svc.confirm(txn.id, "dine_out")

    assert mock_repo.write_correction.called
    call_arg: Correction = mock_repo.write_correction.call_args[0][0]
    assert call_arg.new_category == "dine_out"
    assert call_arg.provenance == CorrectionProvenance.human
    assert call_arg.confirmed_by_human is True
    assert call_arg.quarantined is False
    assert call_arg.confirmed_at is not None


@pytest.mark.asyncio
async def test_confirm_clears_needs_review(user_id: uuid.UUID) -> None:
    """Confirming a row sets transaction.needs_review = False."""
    txn = _make_txn(user_id, needs_review=True)

    mock_session = AsyncMock()
    mock_session.flush = AsyncMock()

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = txn
    mock_session.execute = AsyncMock(return_value=mock_result)

    with patch("app.services.review.queue.CorrectionsRepository") as MockRepo:
        mock_repo = AsyncMock()
        mock_repo.get_by_transaction = AsyncMock(return_value=None)
        mock_repo.write_correction = AsyncMock(side_effect=lambda c: c)
        MockRepo.return_value = mock_repo

        from app.services.review.queue import ReviewQueueService

        svc = ReviewQueueService(mock_session, user_id)
        await svc.confirm(txn.id, "dine_out")

    assert txn.needs_review is False


@pytest.mark.asyncio
async def test_queue_is_rls_scoped(user_id: uuid.UUID) -> None:
    """list_queue uses user_id in the WHERE clause (defense in depth behind RLS)."""
    from app.schemas.review import ReviewQueueResponse

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_result.scalar_one_or_none.return_value = None  # no user_settings → default 'manual'
    mock_session.execute = AsyncMock(return_value=mock_result)

    with patch("app.services.review.queue.CorrectionsRepository") as MockRepo:
        mock_repo = AsyncMock()
        mock_repo.list_quarantined = AsyncMock(return_value=[])
        MockRepo.return_value = mock_repo

        from app.services.review.queue import ReviewQueueService

        svc = ReviewQueueService(mock_session, user_id)
        response = await svc.list_queue()

    # Verify the user_id is forwarded to the repo constructor (defense-in-depth RLS)
    MockRepo.assert_called_with(mock_session, user_id)
    assert isinstance(response, ReviewQueueResponse)
    assert response.items == []


@pytest.mark.asyncio
async def test_confirm_endpoint_commits_session(user_id: uuid.UUID) -> None:
    """The /review/confirm endpoint must commit the session — without it the service's
    flush() rolls back on session teardown and the row reappears on refresh."""
    txn = _make_txn(user_id)

    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.flush = AsyncMock()

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = txn
    mock_session.execute = AsyncMock(return_value=mock_result)

    with patch("app.services.review.queue.CorrectionsRepository") as MockRepo:
        mock_repo = AsyncMock()
        mock_repo.get_by_transaction = AsyncMock(return_value=None)
        mock_repo.write_correction = AsyncMock(side_effect=lambda c: c)
        MockRepo.return_value = mock_repo

        from app.api.review import confirm_review
        from app.schemas.review import ConfirmRequest

        body = ConfirmRequest(transaction_id=txn.id, category="dine_out")
        await confirm_review(body, user=MagicMock(id=str(user_id)), session=mock_session)

    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_relabel_all_endpoint_enqueues_job(user_id: uuid.UUID) -> None:
    """The /review/relabel-all endpoint enqueues a batch relabel job for the caller."""
    mock_session = AsyncMock()

    fake_queue = MagicMock()
    fake_queue.enqueue = MagicMock()

    with patch("app.api.review.get_recompute_queue", return_value=fake_queue):
        from app.api.review import relabel_all

        response = await relabel_all(user=MagicMock(id=str(user_id)), session=mock_session)

    fake_queue.enqueue.assert_called_once()
    call_args = fake_queue.enqueue.call_args
    assert call_args[0][0] == "workers.relabel.run_batch_relabel"
    assert call_args.kwargs["kwargs"]["user_id"] == str(user_id)
    assert response.queued is True
