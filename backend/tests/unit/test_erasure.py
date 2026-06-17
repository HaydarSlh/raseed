"""Unit tests: ErasureService — all-table purge, Redis cleanup, audit entry (Phase 6, FR-008/FR-009)."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from app.schemas.erasure import ErasureResponse
from app.services.erasure import ErasureService, _USER_TABLES


@pytest.fixture
def mock_session() -> AsyncMock:
    session = AsyncMock()

    # session.begin() must return an async context manager object (not a coroutine)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=None)
    cm.__aexit__ = AsyncMock(return_value=False)
    session.begin = MagicMock(return_value=cm)

    result_mock = MagicMock()
    result_mock.rowcount = 3
    session.execute = AsyncMock(return_value=result_mock)
    return session


@pytest.mark.asyncio
async def test_erase_deletes_all_user_tables(mock_session: AsyncMock) -> None:
    """Service must execute DELETE on every user-scoped table plus users itself."""
    user_id = uuid.uuid4()
    service = ErasureService(mock_session)

    with patch.object(service, "_purge_redis", AsyncMock(return_value=2)):
        with patch.object(service, "_write_audit", AsyncMock(return_value=uuid.uuid4())):
            await service.erase_user(user_id)

    executed_sqls = [str(call_args[0][0]) for call_args in mock_session.execute.call_args_list]
    for table in _USER_TABLES:
        assert any(table in sql for sql in executed_sqls), f"No DELETE found for table '{table}'"
    assert any("users" in sql for sql in executed_sqls), "No DELETE found for 'users' table"


@pytest.mark.asyncio
async def test_erase_invalidates_redis_sessions(mock_session: AsyncMock) -> None:
    """Service must scan and delete Redis keys matching the user's pattern."""
    user_id = uuid.uuid4()
    service = ErasureService(mock_session)

    fake_redis = AsyncMock()
    fake_redis.scan = AsyncMock(return_value=(0, [f"raseed:write_rate:{user_id}", f"raseed:session:{user_id}"]))
    fake_redis.delete = AsyncMock(return_value=1)

    with patch("app.infra.redis.get_redis", return_value=fake_redis), \
         patch("app.services.erasure.get_redis", return_value=fake_redis):
        with patch.object(service, "_write_audit", AsyncMock(return_value=uuid.uuid4())):
            response = await service.erase_user(user_id)

    assert fake_redis.scan.called
    assert response.deleted_counts is not None


@pytest.mark.asyncio
async def test_erase_writes_audit_entry(mock_session: AsyncMock) -> None:
    """Service must create an ErasureAudit row with status='completed'."""
    user_id = uuid.uuid4()
    service = ErasureService(mock_session)

    with patch.object(service, "_purge_redis", AsyncMock(return_value=0)):
        with patch("app.services.erasure.ErasureAudit") as MockAudit:
            audit_instance = MagicMock()
            audit_instance.id = uuid.uuid4()
            MockAudit.return_value = audit_instance
            await service.erase_user(user_id)

    MockAudit.assert_called_once()
    kwargs = MockAudit.call_args[1]
    assert kwargs["user_id"] == user_id
    assert kwargs["status"] == "completed"
    mock_session.add.assert_called_with(audit_instance)


@pytest.mark.asyncio
async def test_erase_returns_correct_counts(mock_session: AsyncMock) -> None:
    """ErasureResponse must include per_store_counts with non-negative row counts."""
    user_id = uuid.uuid4()
    service = ErasureService(mock_session)
    audit_id = uuid.uuid4()

    with patch.object(service, "_purge_redis", AsyncMock(return_value=5)):
        with patch.object(service, "_write_audit", AsyncMock(return_value=audit_id)):
            response = await service.erase_user(user_id)

    assert isinstance(response, ErasureResponse)
    assert response.status == "completed"
    assert response.audit_id == audit_id
    for table in _USER_TABLES:
        assert table in response.deleted_counts
        assert response.deleted_counts[table] >= 0
