"""Integration test: POST /chat for enumerable questions returns exact figure + route: deterministic (no LLM)."""

from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

# These tests require a Postgres service but no live LLM or compose stack.
# They are skipped in environments where USE_FAKE_LLM is not available.

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def client():
    """Build the FastAPI test client with a fake session and fake LLM."""
    from fastapi.testclient import TestClient

    from main import create_app

    app = create_app()
    # Override auth and session deps
    from app.api.deps import current_active_user
    from app.db.session import get_rls_session

    fake_user = MagicMock()
    fake_user.id = uuid.uuid4()

    mock_session = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one.return_value = 1234.56
    result_mock.scalars.return_value.all.return_value = []
    mock_session.execute.return_value = result_mock

    app.dependency_overrides[current_active_user] = lambda: fake_user
    app.dependency_overrides[get_rls_session] = lambda: mock_session
    yield TestClient(app)
    app.dependency_overrides.clear()


async def test_balance_query_is_deterministic(client) -> None:
    """Balance question must return route: deterministic with the exact figure."""
    session_id = str(uuid.uuid4())
    response = client.post("/chat", json={"message": "What's my balance?", "session_id": session_id})
    assert response.status_code == 200

    lines = [line for line in response.text.strip().split("\n") if line]
    final_line = json.loads(lines[-1])
    assert final_line.get("route") == "deterministic"
    assert final_line.get("done") is True

    # Check the answer contains the balance figure
    first_line = json.loads(lines[0])
    assert "1,234.56" in first_line.get("delta", "")
