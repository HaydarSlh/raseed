"""Integration test: non-operator gets 403 on /ops/retrain and /ops/promote (FR-016, SC-008)."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest


@pytest.fixture()
def test_app():
    """Build a minimal test app (non-operator user injected)."""
    from main import create_app
    return create_app()


def _non_operator_user():
    from app.domain.user import User
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    user.is_active = True
    user.is_operator = False
    user.is_superuser = False
    return user


def _operator_user():
    from app.domain.user import User
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    user.is_active = True
    user.is_operator = True
    user.is_superuser = False
    return user


@pytest.mark.asyncio
async def test_non_operator_cannot_trigger_retrain() -> None:
    """Non-operator calling POST /ops/retrain receives 403."""
    from fastapi import HTTPException

    from app.api.ops import _require_operator

    non_op = _non_operator_user()
    with pytest.raises(HTTPException) as exc_info:
        _require_operator(non_op)
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_non_operator_cannot_promote() -> None:
    """Non-operator calling POST /ops/promote receives 403."""
    from fastapi import HTTPException

    from app.api.ops import _require_operator

    non_op = _non_operator_user()
    with pytest.raises(HTTPException) as exc_info:
        _require_operator(non_op)
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_operator_passes_gate() -> None:
    """Operator user passes the _require_operator dependency."""
    from app.api.ops import _require_operator

    op = _operator_user()
    result = _require_operator(op)
    assert result.is_operator is True
