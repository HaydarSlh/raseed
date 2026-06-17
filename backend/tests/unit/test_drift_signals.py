"""Unit tests: drift signal math — PSI + new-merchant; primary crossing → enqueue + alert; secondary → alert only, no retrain (FR-018/019, R4)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


def _make_settings(
    mean_conf_min: float = 0.70,
    correction_rate_max: float = 0.20,
    psi_max: float = 0.20,
    new_merchant_rate_max: float = 0.15,
) -> MagicMock:
    s = MagicMock()
    s.drift_mean_confidence_min = mean_conf_min
    s.drift_correction_rate_max = correction_rate_max
    s.drift_psi_max = psi_max
    s.drift_new_merchant_rate_max = new_merchant_rate_max
    return s


@pytest.mark.asyncio
async def test_primary_confidence_crossing_triggers_retrain() -> None:
    """Mean confidence below threshold → primary signal fired → retrain enqueued."""
    from app.workers.drift import compute_drift_signals

    signals = compute_drift_signals(
        mean_confidence=0.50,  # below 0.70 threshold
        correction_rate=0.05,
        psi=0.05,
        new_merchant_rate=0.05,
        category_histogram={"groceries": 0.5, "dine_out": 0.5},
        training_histogram={"groceries": 0.5, "dine_out": 0.5},
        seen_merchants={"TESCO", "AMAZON"},
        window_merchants={"TESCO", "AMAZON"},
        settings=_make_settings(),
    )

    assert signals["fired"] is True
    assert "mean_confidence" in signals["fired_signals"]
    assert signals["triggered_retrain"] is True


@pytest.mark.asyncio
async def test_primary_correction_rate_crossing_triggers_retrain() -> None:
    """Correction rate above threshold → primary signal fired → retrain enqueued."""
    from app.workers.drift import compute_drift_signals

    signals = compute_drift_signals(
        mean_confidence=0.80,
        correction_rate=0.30,  # above 0.20 threshold
        psi=0.05,
        new_merchant_rate=0.05,
        category_histogram={"groceries": 1.0},
        training_histogram={"groceries": 1.0},
        seen_merchants={"TESCO"},
        window_merchants={"TESCO"},
        settings=_make_settings(),
    )

    assert signals["fired"] is True
    assert "correction_rate" in signals["fired_signals"]
    assert signals["triggered_retrain"] is True


@pytest.mark.asyncio
async def test_secondary_only_crossing_does_not_trigger_retrain() -> None:
    """PSI above threshold (secondary) → alert fired, NO retrain enqueued (FR-019, R4)."""
    from app.workers.drift import compute_drift_signals

    signals = compute_drift_signals(
        mean_confidence=0.80,  # fine
        correction_rate=0.05,  # fine
        psi=0.30,  # above 0.20 threshold (secondary)
        new_merchant_rate=0.05,
        category_histogram={"groceries": 0.8, "travel": 0.2},
        training_histogram={"groceries": 0.3, "dine_out": 0.7},
        seen_merchants={"TESCO"},
        window_merchants={"TESCO"},
        settings=_make_settings(),
    )

    assert signals["fired"] is True
    assert "psi" in signals["fired_signals"]
    assert signals["triggered_retrain"] is False  # secondary only


@pytest.mark.asyncio
async def test_no_signal_no_retrain() -> None:
    """All signals within thresholds → nothing fired."""
    from app.workers.drift import compute_drift_signals

    signals = compute_drift_signals(
        mean_confidence=0.85,
        correction_rate=0.05,
        psi=0.05,
        new_merchant_rate=0.05,
        category_histogram={"groceries": 0.5, "dine_out": 0.5},
        training_histogram={"groceries": 0.5, "dine_out": 0.5},
        seen_merchants={"TESCO"},
        window_merchants={"TESCO"},
        settings=_make_settings(),
    )

    assert signals["fired"] is False
    assert signals["triggered_retrain"] is False


def test_psi_math_identical_distributions() -> None:
    """PSI of identical distributions is 0."""
    from app.workers.drift import compute_psi

    hist = {"groceries": 0.5, "dine_out": 0.5}
    assert compute_psi(hist, hist) == pytest.approx(0.0, abs=1e-6)


def test_new_merchant_rate_all_known() -> None:
    """New-merchant rate is 0 when all window merchants are in the training set."""
    from app.workers.drift import compute_new_merchant_rate

    training = {"TESCO", "AMAZON", "UBER"}
    window = {"TESCO", "AMAZON"}
    assert compute_new_merchant_rate(window, training) == pytest.approx(0.0)


def test_new_merchant_rate_all_new() -> None:
    """New-merchant rate is 1.0 when no window merchants were in training set."""
    from app.workers.drift import compute_new_merchant_rate

    training = {"TESCO"}
    window = {"UNKNOWN_X", "UNKNOWN_Y"}
    assert compute_new_merchant_rate(window, training) == pytest.approx(1.0)
