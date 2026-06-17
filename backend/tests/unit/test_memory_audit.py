"""Unit tests: write_memory audit trail, user-scoping, single durable-memory path (FR-018/019)."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.agent.tools.registry import dispatch


@pytest.fixture(autouse=True)
def _register_memory_tool() -> None:
    import app.services.agent.tools.memory  # noqa: F401


@pytest.mark.asyncio
async def test_write_memory_creates_audit_log() -> None:
    """write_memory must produce exactly one AuditLog row per call (FR-019)."""
    user_id = uuid.uuid4()
    mock_session = AsyncMock()
    added_objects: list = []

    def _capture_add(obj: object) -> None:
        added_objects.append(obj)

    mock_session.add = MagicMock(side_effect=_capture_add)  # add() is sync in SQLAlchemy
    mock_session.flush = AsyncMock()

    with (
        patch("app.services.agent.tools.memory.get_embedder") as mock_embedder_fn,
        patch("app.services.agent.tools.memory.MemoryRepository") as MockMemRepo,
        patch("app.services.agent.tools.memory.check_write_rate", AsyncMock()),
    ):
        fake_embedder = AsyncMock()
        fake_embedder.embed = AsyncMock(return_value=[0.1] * 768)
        mock_embedder_fn.return_value = fake_embedder

        fake_mem = MagicMock()
        fake_mem.id = uuid.uuid4()
        fake_mem.created_at = "2026-06-17T00:00:00"
        MockMemRepo.return_value.upsert = AsyncMock(return_value=fake_mem)

        result = await dispatch(
            "write_memory",
            {"content": "I prefer conservative advice", "_session": mock_session, "_user_id": user_id},
        )

    assert "id" in result
    # Exactly one AuditLog must be added
    from app.domain.audit import AuditLog
    audit_rows = [o for o in added_objects if isinstance(o, AuditLog)]
    assert len(audit_rows) == 1
    assert audit_rows[0].action == "write_memory"
    assert audit_rows[0].user_id == user_id


@pytest.mark.asyncio
async def test_write_memory_requires_content() -> None:
    """Missing or empty content must be rejected (schema validation)."""
    result = await dispatch("write_memory", {"content": ""})
    assert "error" in result


@pytest.mark.asyncio
async def test_write_memory_rejects_oversized_content() -> None:
    result = await dispatch("write_memory", {"content": "x" * 1025})
    assert "error" in result


@pytest.mark.asyncio
async def test_write_memory_enforces_user_scope() -> None:
    """Without session/user context, returns error — never writes cross-user."""
    result = await dispatch("write_memory", {"content": "test"})
    assert isinstance(result, dict)
    # With no session, the tool should return an error, not write anything
    assert "error" in result or "id" not in result
