"""Unit tests for the ingestion service: rule routing, confidence gate, dedup logic.

Uses unittest.mock so no DB or model-server is required (all IO is isolated).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from app.schemas.ingestion import IngestResult, ParsedRow
from app.services.ingestion import _normalize, _passes_gate, ingest_transactions


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def sample_row() -> ParsedRow:
    return ParsedRow(
        occurred_at=datetime(2026, 6, 1),
        amount=Decimal("-12.50"),
        description="LIDL GB NOTTINGHAM",
        currency="GBP",
    )


def test_normalize():
    assert _normalize("  LIDL GB  ") == "lidl gb"


def test_passes_gate_known_category():
    # groceries threshold is 0.93
    assert _passes_gate("groceries", 0.95) is True
    assert _passes_gate("groceries", 0.90) is False


def test_passes_gate_always_review():
    assert _passes_gate("services", 0.99) is False
    assert _passes_gate("entertainment", 1.0) is False


@pytest.mark.asyncio
async def test_rule_matched_skips_model(user_id, sample_row):
    salary_row = ParsedRow(
        occurred_at=datetime(2026, 6, 1),
        amount=Decimal("2000.00"),
        description="Monthly SALARY PAYROLL",
        currency="GBP",
    )
    mock_repo = AsyncMock()
    mock_repo.insert_skip_duplicates = AsyncMock(return_value=1)

    mock_client = AsyncMock()
    mock_client.classify = AsyncMock(return_value=[])

    with patch("app.services.ingestion.enqueue_recompute"):
        result = await ingest_transactions(user_id, [salary_row], mock_repo, mock_client)

    # classify must NOT have been called (rule matched)
    mock_client.classify.assert_not_called()
    assert result.ingested == 1


@pytest.mark.asyncio
async def test_model_below_threshold_flagged(user_id):
    # Description must NOT match any high-precision rule in rules.py, or it would
    # short-circuit to provenance='rule' (confidence 1.0, never flagged) and never
    # reach the model. A small independent merchant is deliberately left to the model.
    model_routed_row = ParsedRow(
        occurred_at=datetime(2026, 6, 1),
        amount=Decimal("-12.50"),
        description="THE CORNER MINIMART LDN",
        currency="GBP",
    )
    mock_repo = AsyncMock()
    mock_repo.insert_skip_duplicates = AsyncMock(return_value=1)

    mock_client = AsyncMock()
    # Return low confidence for groceries (threshold 0.93)
    mock_client.classify = AsyncMock(return_value=[{"label": "groceries", "confidence": 0.85}])

    with patch("app.services.ingestion.enqueue_recompute"):
        result = await ingest_transactions(user_id, [model_routed_row], mock_repo, mock_client)

    assert result.needs_review == 1
    assert result.ingested == 1


@pytest.mark.asyncio
async def test_duplicate_skipped(user_id, sample_row):
    mock_repo = AsyncMock()
    mock_repo.insert_skip_duplicates = AsyncMock(return_value=0)

    mock_client = AsyncMock()
    mock_client.classify = AsyncMock(return_value=[{"label": "groceries", "confidence": 0.95}])

    with patch("app.services.ingestion.enqueue_recompute"):
        result = await ingest_transactions(user_id, [sample_row], mock_repo, mock_client)

    assert result.duplicates_skipped == 1
    assert result.ingested == 0


@pytest.mark.asyncio
async def test_empty_rows(user_id):
    mock_repo = AsyncMock()
    mock_client = AsyncMock()

    result = await ingest_transactions(user_id, [], mock_repo, mock_client)

    assert result == IngestResult()
    mock_repo.insert_skip_duplicates.assert_not_called()


@pytest.mark.asyncio
async def test_recompute_only_on_insert(user_id, sample_row):
    mock_repo = AsyncMock()
    mock_repo.insert_skip_duplicates = AsyncMock(return_value=0)  # all duplicates

    mock_client = AsyncMock()
    mock_client.classify = AsyncMock(return_value=[{"label": "groceries", "confidence": 0.95}])

    with patch("app.services.ingestion.enqueue_recompute") as mock_enqueue:
        await ingest_transactions(user_id, [sample_row], mock_repo, mock_client)

    mock_enqueue.assert_not_called()
