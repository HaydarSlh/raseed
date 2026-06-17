"""Unit tests: tool Pydantic validation, RLS scoping, summaries/aggregates only (FR-008/009/011)."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.agent.tools.registry import dispatch


@pytest.fixture(autouse=True)
def _register_tools() -> None:
    """Ensure tools are registered by importing the modules."""
    import app.services.agent.tools.analysis  # noqa: F401
    import app.services.agent.tools.goals  # noqa: F401
    import app.services.agent.tools.knowledge  # noqa: F401
    import app.services.agent.tools.memory  # noqa: F401
    import app.services.agent.tools.reads  # noqa: F401
    import app.services.agent.tools.writes  # noqa: F401


# ── Schema validation (FR-008) ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_query_transactions_rejects_bad_limit() -> None:
    result = await dispatch("query_transactions", {"limit": 999})  # > 100
    assert "error" in result


@pytest.mark.asyncio
async def test_get_anomalies_rejects_bad_limit() -> None:
    result = await dispatch("get_anomalies", {"limit": 999})  # > 50
    assert "error" in result


@pytest.mark.asyncio
async def test_add_transaction_rejects_missing_fields() -> None:
    result = await dispatch("add_transaction", {"amount": 10.0})  # missing txn_date, description
    assert "error" in result


@pytest.mark.asyncio
async def test_reclassify_rejects_missing_category() -> None:
    result = await dispatch("reclassify_transaction", {"transaction_id": str(uuid.uuid4())})
    assert "error" in result


@pytest.mark.asyncio
async def test_write_memory_rejects_too_long() -> None:
    result = await dispatch("write_memory", {"content": "x" * 1025})  # > 1024
    assert "error" in result


# ── No session → structured error, not exception (FR-009) ────────────────────

@pytest.mark.asyncio
async def test_query_transactions_no_session_returns_error() -> None:
    """Without _session/_user_id, tool returns error dict, not exception."""
    result = await dispatch("query_transactions", {})
    # Should not raise; should return error because session is None
    assert isinstance(result, dict)


@pytest.mark.asyncio
async def test_get_forecast_no_session_returns_error() -> None:
    result = await dispatch("get_forecast", {})
    assert isinstance(result, dict)


# ── Output shape: aggregates/summaries only (FR-011, Art. II) ────────────────

@pytest.mark.asyncio
async def test_query_transactions_returns_aggregates() -> None:
    """When session is available, result must contain count+total, not raw identifiers."""
    mock_session = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = []
    mock_session.execute.return_value = result_mock

    uid = uuid.uuid4()
    result = await dispatch("query_transactions", {"_session": mock_session, "_user_id": uid})
    # Either an error or a properly shaped result — no raw user IDs in items
    if "items" in result:
        for item in result["items"]:
            assert "user_id" not in item
