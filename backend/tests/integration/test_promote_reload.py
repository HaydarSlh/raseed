"""Integration test: operator promote → registry swap + model-server reload; SHA mismatch aborts (FR-017)."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.domain.model_registry import ModelRegistry, ModelStatus
from app.domain.retrain_run import RetrainRun, RunStatus, TriggerReason


def _make_champion() -> ModelRegistry:
    return ModelRegistry(
        id=uuid.uuid4(),
        name="categorizer",
        version="v2.0.0",
        sha256="abc123",
        status=ModelStatus.champion,
    )


def _make_challenger(retrain_run_id: uuid.UUID) -> ModelRegistry:
    return ModelRegistry(
        id=uuid.uuid4(),
        name="categorizer",
        version="v2.1.0",
        sha256="def456",
        status=ModelStatus.challenger,
        retrain_run_id=retrain_run_id,
    )


def _make_run(verdict: str = "beats") -> RetrainRun:
    return RetrainRun(
        id=uuid.uuid4(),
        trigger_reason=TriggerReason.manual,
        idempotency_key="test-key",
        status=RunStatus.completed,
        champion_macro_f1=0.89,
        challenger_macro_f1=0.92,
        gate_verdict=verdict,
    )


@pytest.mark.asyncio
async def test_promote_swaps_registry_and_reloads() -> None:
    """Operator promote: champion→archived, challenger→champion, model-server reloads."""
    operator_id = uuid.uuid4()
    run = _make_run(verdict="beats")
    champion = _make_champion()
    challenger = _make_challenger(run.id)

    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()

    with patch("app.services.lifecycle.promote.ModelRegistryRepository") as MockReg, \
         patch("app.services.lifecycle.promote.RetrainRunsRepository") as MockRuns, \
         patch("app.services.lifecycle.promote.GateService") as MockGate, \
         patch("app.services.lifecycle.promote.ModelServerClient") as MockClient:

        mock_reg = AsyncMock()
        mock_reg.get_by_id = AsyncMock(return_value=challenger)
        mock_reg.get_champion = AsyncMock(return_value=champion)
        mock_reg.promote = AsyncMock(return_value=(challenger, champion))
        MockReg.return_value = mock_reg

        MockRuns.return_value = AsyncMock()

        mock_gate = AsyncMock()
        mock_gate.challenger_beats_champion = AsyncMock(return_value=True)
        MockGate.return_value = mock_gate

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.reload = AsyncMock(return_value={"status": "reloaded", "sha256": "def456"})
        MockClient.return_value = mock_client

        from app.services.lifecycle.promote import PromoteService
        svc = PromoteService(mock_session)
        result = await svc.promote(challenger.id, operator_id)

    assert result.promoted == challenger.id
    assert result.archived == champion.id
    assert result.model_server_reloaded is True
    mock_client.reload.assert_called_with("def456")


@pytest.mark.asyncio
async def test_promote_aborts_on_reload_failure() -> None:
    """SHA mismatch on /reload → rollback the registry swap, keep prior champion."""
    operator_id = uuid.uuid4()
    run = _make_run(verdict="beats")
    champion = _make_champion()
    challenger = _make_challenger(run.id)

    mock_session = AsyncMock()
    mock_session.rollback = AsyncMock()

    with patch("app.services.lifecycle.promote.ModelRegistryRepository") as MockReg, \
         patch("app.services.lifecycle.promote.RetrainRunsRepository") as MockRuns, \
         patch("app.services.lifecycle.promote.GateService") as MockGate, \
         patch("app.services.lifecycle.promote.ModelServerClient") as MockClient:

        mock_reg = AsyncMock()
        mock_reg.get_by_id = AsyncMock(return_value=challenger)
        mock_reg.get_champion = AsyncMock(return_value=champion)
        mock_reg.promote = AsyncMock(return_value=(challenger, champion))
        MockReg.return_value = mock_reg

        MockRuns.return_value = AsyncMock()

        mock_gate = AsyncMock()
        mock_gate.challenger_beats_champion = AsyncMock(return_value=True)
        MockGate.return_value = mock_gate

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.reload = AsyncMock(side_effect=Exception("sha256 mismatch"))
        MockClient.return_value = mock_client

        from app.core.exceptions import UpstreamError
        from app.services.lifecycle.promote import PromoteService

        svc = PromoteService(mock_session)
        with pytest.raises(UpstreamError, match="reload failed"):
            await svc.promote(challenger.id, operator_id)

    mock_session.rollback.assert_called()
