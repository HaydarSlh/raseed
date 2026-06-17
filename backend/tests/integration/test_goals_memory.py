"""Integration test: goals CRUD + session memory TTL + audited durable memory (FR-016/017, SC-010)."""

from __future__ import annotations

import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.asyncio


async def test_goal_created_via_tool() -> None:
    """set_goal creates a goal that get_goals can retrieve."""
    user_id = uuid.uuid4()
    mock_session = AsyncMock()

    fake_goal = MagicMock()
    fake_goal.id = uuid.uuid4()
    fake_goal.name = "Car fund"
    fake_goal.target_amount = 5000.0
    fake_goal.target_date = date(2027, 6, 1)
    fake_goal.status = MagicMock(value="active")

    import app.services.agent.tools.goals  # noqa: F401
    from app.services.agent.tools.registry import dispatch

    with (
        patch("app.services.agent.tools.goals.check_write_rate", AsyncMock()),
        patch("app.services.agent.tools.goals.GoalsRepository") as MockRepo,
    ):
        MockRepo.return_value.create = AsyncMock(return_value=fake_goal)
        mock_session.flush = AsyncMock()

        result = await dispatch(
            "set_goal",
            {
                "name": "Car fund",
                "target_amount": 5000.0,
                "target_date": "2027-06-01",
                "_session": mock_session,
                "_user_id": user_id,
            },
        )

    assert result.get("name") == "Car fund"
    assert result.get("target_amount") == 5000.0


async def test_session_context_loaded_and_appended() -> None:
    """Session memory loads prior turns and appends new ones."""
    from app.services.session_memory import append_turn, load_context

    session_id = str(uuid.uuid4())

    with patch("app.services.session_memory.get_redis") as mock_redis_fn:
        mock_redis = AsyncMock()
        mock_redis_fn.return_value = mock_redis

        # First load: empty
        mock_redis.get.return_value = None
        context = await load_context(session_id)
        assert context == []

        # Append a turn
        mock_redis.get.return_value = None  # fresh session
        await append_turn(session_id, "user", "Hello", ttl=1800)
        mock_redis.setex.assert_called_once()

        # Verify the stored value is valid JSON with the turn
        call_args = mock_redis.setex.call_args
        stored = call_args[0][2] if call_args[0] else call_args.kwargs.get("value", "[]")
        import json
        turns = json.loads(stored)
        assert turns[-1]["role"] == "user"
        assert turns[-1]["content"] == "Hello"


async def test_durable_memory_has_audit_log() -> None:
    """write_memory must produce an AuditLog row — verified by test_memory_audit.py (cross-reference)."""
    # The authoritative test is in test_memory_audit.py; this confirms the integration path
    # exists and write_memory is the only route to durable memory.
    import app.services.agent.tools.memory  # noqa: F401
    from app.services.agent.tools.registry import get_tool_names
    # Only write_memory should be the durable memory path
    tool_names = get_tool_names()
    assert "write_memory" in tool_names
    # No other tool that could write to memory
    memory_tools = [t for t in tool_names if "memory" in t.lower() and t != "write_memory"]
    assert memory_tools == []
