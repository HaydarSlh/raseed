"""Unit tests: gate service — challenger strictly beats champion → 'beats'; tie → 'does_not_beat' (FR-015)."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.retrain_run import RetrainRun, RunStatus, TriggerReason


def _make_run(
    champion_f1: float,
    challenger_f1: float,
    verdict: str,
) -> RetrainRun:
    return RetrainRun(
        id=uuid.uuid4(),
        trigger_reason=TriggerReason.manual,
        idempotency_key="test-key",
        status=RunStatus.completed,
        champion_macro_f1=champion_f1,
        challenger_macro_f1=challenger_f1,
        gate_verdict=verdict,
    )


@pytest.mark.asyncio
async def test_challenger_beats_champion_returns_true() -> None:
    """gate_verdict='beats' → challenger_beats_champion returns True."""
    run = _make_run(0.89, 0.91, "beats")
    challenger_id = uuid.uuid4()

    mock_session = AsyncMock()

    with patch("app.services.lifecycle.gate.ModelRegistryRepository") as MockReg, \
         patch("app.services.lifecycle.gate.RetrainRunsRepository") as MockRuns:

        mock_reg = AsyncMock()
        mock_challenger = MagicMock()
        mock_challenger.retrain_run_id = run.id
        mock_reg.get_by_id = AsyncMock(return_value=mock_challenger)
        MockReg.return_value = mock_reg

        mock_runs = AsyncMock()
        mock_runs.get_by_id = AsyncMock(return_value=run)
        MockRuns.return_value = mock_runs

        from app.services.lifecycle.gate import GateService
        svc = GateService(mock_session)
        result = await svc.challenger_beats_champion(challenger_id)

    assert result is True


@pytest.mark.asyncio
async def test_tie_does_not_beat() -> None:
    """gate_verdict='does_not_beat' → challenger_beats_champion returns False (tie rule)."""
    run = _make_run(0.90, 0.90, "does_not_beat")
    challenger_id = uuid.uuid4()

    mock_session = AsyncMock()

    with patch("app.services.lifecycle.gate.ModelRegistryRepository") as MockReg, \
         patch("app.services.lifecycle.gate.RetrainRunsRepository") as MockRuns:

        mock_reg = AsyncMock()
        mock_challenger = MagicMock()
        mock_challenger.retrain_run_id = run.id
        mock_reg.get_by_id = AsyncMock(return_value=mock_challenger)
        MockReg.return_value = mock_reg

        mock_runs = AsyncMock()
        mock_runs.get_by_id = AsyncMock(return_value=run)
        MockRuns.return_value = mock_runs

        from app.services.lifecycle.gate import GateService
        svc = GateService(mock_session)
        result = await svc.challenger_beats_champion(challenger_id)

    assert result is False


@pytest.mark.asyncio
async def test_no_retrain_run_returns_false() -> None:
    """If the challenger has no linked retrain_run, promotion is denied."""
    challenger_id = uuid.uuid4()
    mock_session = AsyncMock()

    with patch("app.services.lifecycle.gate.ModelRegistryRepository") as MockReg, \
         patch("app.services.lifecycle.gate.RetrainRunsRepository") as MockRuns:

        mock_reg = AsyncMock()
        mock_challenger = MagicMock()
        mock_challenger.retrain_run_id = None
        mock_reg.get_by_id = AsyncMock(return_value=mock_challenger)
        MockReg.return_value = mock_reg
        MockRuns.return_value = AsyncMock()

        from app.services.lifecycle.gate import GateService
        svc = GateService(mock_session)
        result = await svc.challenger_beats_champion(challenger_id)

    assert result is False
