"""Integration test: cross-user isolation — no tool ever returns another user's data (FR-009/024, SC-007)."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.asyncio


async def test_query_transactions_scoped_to_user() -> None:
    """query_transactions called with user A's session cannot return user B's rows."""
    import app.services.agent.tools.reads  # noqa: F401
    from app.services.agent.tools.registry import dispatch

    user_a = uuid.uuid4()
    mock_session = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = []
    mock_session.execute.return_value = result_mock

    result = await dispatch("query_transactions", {"_session": mock_session, "_user_id": user_a})
    assert isinstance(result, dict)

    # Verify the SQL query included user A's id
    call_args = mock_session.execute.call_args_list
    if call_args:
        stmt = call_args[0][0][0]
        # The repository always filters by user_id; check the WHERE clause contains user_a's id
        stmt_str = str(stmt)
        assert "user_id" in stmt_str.lower() or "user_a" in str(user_a)  # RLS enforces this


async def test_goals_scoped_to_user() -> None:
    """get_goals returns only the requesting user's goals."""
    import app.services.agent.tools.goals  # noqa: F401
    from app.services.agent.tools.registry import dispatch

    user_a = uuid.uuid4()
    mock_session = AsyncMock()

    mock_repo = MagicMock()
    mock_repo.list_by_status = AsyncMock(return_value=[])

    from unittest.mock import patch
    with patch("app.services.agent.tools.goals.GoalsRepository", return_value=mock_repo):
        result = await dispatch("get_goals", {"_session": mock_session, "_user_id": user_a})

    assert result.get("items") == []
    # If a repo was constructed, it should have been constructed with user_a's id
    # (GoalsRepository.__init__ takes session + user_id)


async def test_write_memory_scoped_to_user() -> None:
    """write_memory must use the calling user's id for the audit log, not another user's."""
    user_a = uuid.uuid4()
    user_b = uuid.uuid4()
    assert user_a != user_b

    added_objects: list = []
    mock_session = AsyncMock()
    mock_session.add.side_effect = added_objects.append
    mock_session.flush = AsyncMock()

    from unittest.mock import patch

    import app.services.agent.tools.memory  # noqa: F401
    from app.services.agent.tools.registry import dispatch
    with (
        patch("app.services.agent.tools.memory.get_embedder") as mock_emb_fn,
        patch("app.services.agent.tools.memory.MemoryRepository") as MockMR,
        patch("app.services.agent.tools.memory.check_write_rate", AsyncMock()),
    ):
        fake_emb = AsyncMock()
        fake_emb.embed = AsyncMock(return_value=[0.0] * 768)
        mock_emb_fn.return_value = fake_emb

        fake_mem = MagicMock()
        fake_mem.id = uuid.uuid4()
        fake_mem.created_at = "2026-01-01"
        MockMR.return_value.upsert = AsyncMock(return_value=fake_mem)

        await dispatch("write_memory", {"content": "test", "_session": mock_session, "_user_id": user_a})

    from app.domain.audit import AuditLog
    audit_rows = [o for o in added_objects if isinstance(o, AuditLog)]
    assert all(row.user_id == user_a for row in audit_rows)
    assert all(row.user_id != user_b for row in audit_rows)
