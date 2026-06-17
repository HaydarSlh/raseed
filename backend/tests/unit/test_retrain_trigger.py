"""Unit tests: retrain trigger — count/cooldown/manual/drift fire; global idempotency (one job/window); manual force overrides (FR-009, SC-006)."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.retrain_run import RetrainRun, RunStatus, TriggerReason


def _make_run(reason: TriggerReason = TriggerReason.manual) -> RetrainRun:
    return RetrainRun(
        id=uuid.uuid4(),
        trigger_reason=reason,
        idempotency_key=f"retrain:{reason.value}:2026-25",
        status=RunStatus.enqueued,
    )


@pytest.mark.asyncio
async def test_count_trigger_fires_above_threshold() -> None:
    """Correction count >= demo threshold fires a retrain."""
    mock_session = AsyncMock()

    with patch("app.services.lifecycle.trigger.get_redis") as mock_get_redis, \
         patch("app.services.lifecycle.trigger.enqueue_retrain") as mock_enqueue, \
         patch("app.services.lifecycle.trigger.RetrainRunsRepository") as MockRepo:

        mock_redis = AsyncMock()
        mock_redis.exists = AsyncMock(return_value=0)  # no cooldown
        mock_redis.setex = AsyncMock()
        mock_get_redis.return_value = mock_redis

        mock_repo = AsyncMock()
        run = _make_run(TriggerReason.correction_count)
        mock_repo.create_or_get = AsyncMock(return_value=(run, True))
        MockRepo.return_value = mock_repo

        with patch("app.services.lifecycle.trigger.get_settings") as mock_settings:
            settings = MagicMock()
            settings.demo_mode = True
            settings.retrain_threshold_demo = 10
            settings.retrain_cooldown_days = 14
            mock_settings.return_value = settings

            from app.services.lifecycle.trigger import RetrainTriggerService
            svc = RetrainTriggerService(mock_session)
            result_run, enqueued = await svc.trigger_count(confirmed_count=10)

    assert enqueued is True
    assert mock_enqueue.called


@pytest.mark.asyncio
async def test_count_trigger_below_threshold_does_not_fire() -> None:
    """Correction count < demo threshold does not enqueue."""
    mock_session = AsyncMock()

    with patch("app.services.lifecycle.trigger.get_redis") as mock_get_redis, \
         patch("app.services.lifecycle.trigger.enqueue_retrain") as mock_enqueue, \
         patch("app.services.lifecycle.trigger.RetrainRunsRepository") as MockRepo:

        mock_redis = AsyncMock()
        mock_redis.exists = AsyncMock(return_value=0)
        mock_get_redis.return_value = mock_redis
        MockRepo.return_value = AsyncMock()

        with patch("app.services.lifecycle.trigger.get_settings") as mock_settings:
            settings = MagicMock()
            settings.demo_mode = True
            settings.retrain_threshold_demo = 10
            settings.retrain_cooldown_days = 14
            mock_settings.return_value = settings

            from app.services.lifecycle.trigger import RetrainTriggerService
            svc = RetrainTriggerService(mock_session)
            result_run, enqueued = await svc.trigger_count(confirmed_count=5)

    assert enqueued is False
    assert not mock_enqueue.called


@pytest.mark.asyncio
async def test_cooldown_blocks_second_trigger() -> None:
    """Cooldown active → second trigger returns existing run without enqueuing."""
    mock_session = AsyncMock()

    with patch("app.services.lifecycle.trigger.get_redis") as mock_get_redis, \
         patch("app.services.lifecycle.trigger.enqueue_retrain") as mock_enqueue, \
         patch("app.services.lifecycle.trigger.RetrainRunsRepository") as MockRepo:

        mock_redis = AsyncMock()
        mock_redis.exists = AsyncMock(return_value=1)  # cooldown active
        mock_get_redis.return_value = mock_redis

        existing_run = _make_run()
        mock_repo = AsyncMock()
        mock_repo.get_latest = AsyncMock(return_value=existing_run)
        MockRepo.return_value = mock_repo

        with patch("app.services.lifecycle.trigger.get_settings") as mock_settings:
            settings = MagicMock()
            settings.demo_mode = False
            settings.retrain_threshold_prod = 100
            settings.retrain_cooldown_days = 14
            mock_settings.return_value = settings

            from app.services.lifecycle.trigger import RetrainTriggerService
            svc = RetrainTriggerService(mock_session)
            run, enqueued = await svc.trigger_manual(force=False)

    assert enqueued is False
    assert not mock_enqueue.called


@pytest.mark.asyncio
async def test_manual_force_bypasses_cooldown() -> None:
    """force=True overrides the cooldown and resets the key."""
    mock_session = AsyncMock()

    with patch("app.services.lifecycle.trigger.get_redis") as mock_get_redis, \
         patch("app.services.lifecycle.trigger.enqueue_retrain") as mock_enqueue, \
         patch("app.services.lifecycle.trigger.RetrainRunsRepository") as MockRepo:

        mock_redis = AsyncMock()
        mock_redis.exists = AsyncMock(return_value=1)  # cooldown active
        mock_redis.delete = AsyncMock()
        mock_redis.setex = AsyncMock()
        mock_get_redis.return_value = mock_redis

        run = _make_run(TriggerReason.manual)
        mock_repo = AsyncMock()
        mock_repo.create_or_get = AsyncMock(return_value=(run, True))
        MockRepo.return_value = mock_repo

        with patch("app.services.lifecycle.trigger.get_settings") as mock_settings:
            settings = MagicMock()
            settings.demo_mode = False
            settings.retrain_threshold_prod = 100
            settings.retrain_cooldown_days = 14
            mock_settings.return_value = settings

            from app.services.lifecycle.trigger import RetrainTriggerService
            svc = RetrainTriggerService(mock_session)
            result_run, enqueued = await svc.trigger_manual(force=True)

    assert enqueued is True
    mock_redis.delete.assert_called()  # cooldown reset
    assert mock_enqueue.called


@pytest.mark.asyncio
async def test_idempotent_key_returns_existing_run() -> None:
    """Same idempotency key → existing run returned, not a new one enqueued."""
    mock_session = AsyncMock()

    with patch("app.services.lifecycle.trigger.get_redis") as mock_get_redis, \
         patch("app.services.lifecycle.trigger.enqueue_retrain") as mock_enqueue, \
         patch("app.services.lifecycle.trigger.RetrainRunsRepository") as MockRepo:

        mock_redis = AsyncMock()
        mock_redis.exists = AsyncMock(return_value=0)
        mock_get_redis.return_value = mock_redis

        existing_run = _make_run(TriggerReason.drift)
        mock_repo = AsyncMock()
        mock_repo.create_or_get = AsyncMock(return_value=(existing_run, False))  # already exists
        MockRepo.return_value = mock_repo

        with patch("app.services.lifecycle.trigger.get_settings") as mock_settings:
            settings = MagicMock()
            settings.demo_mode = False
            settings.retrain_threshold_prod = 100
            settings.retrain_cooldown_days = 14
            mock_settings.return_value = settings

            from app.services.lifecycle.trigger import RetrainTriggerService
            svc = RetrainTriggerService(mock_session)
            run, enqueued = await svc.trigger_drift()

    assert enqueued is False
    assert not mock_enqueue.called
