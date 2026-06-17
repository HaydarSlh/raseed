"""CI gate #2: forecaster MAE must not exceed the day-of-week baseline MAE.

Loads the committed golden fixture from tests/golden/forecasting/ and verifies
the forecasting service beats the trivial baseline (constitution Art. V, R9).

No DB, no network, no Docker — the fixture is pure parquet (CI-stack-independent).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from pathlib import Path

import pytest

GOLDEN_DIR = Path(__file__).parent / "golden" / "forecasting"


def _has_fixtures() -> bool:
    return (GOLDEN_DIR / "history.parquet").exists() and (GOLDEN_DIR / "expected_horizon.parquet").exists()


@pytest.mark.skipif(not _has_fixtures(), reason="Golden fixtures not generated yet — run generate_fixture.py")
def test_forecaster_beats_baseline() -> None:
    """Forecaster MAE <= day-of-week baseline MAE on the committed golden fixture."""
    import pandas as pd

    from app.domain.transaction import Provenance, Transaction
    from app.services.analytics import _day_of_week_baseline, compute_forecast

    history_df = pd.read_parquet(GOLDEN_DIR / "history.parquet")
    expected_df = pd.read_parquet(GOLDEN_DIR / "expected_horizon.parquet")

    user_ids = history_df["user_id"].unique()
    baseline_maes: list[float] = []
    forecaster_maes: list[float] = []

    for uid in user_ids:
        user_hist = history_df[history_df["user_id"] == uid].copy()
        user_exp = expected_df[expected_df["user_id"] == uid].copy()
        if user_hist.empty or user_exp.empty:
            continue

        # Build Transaction stubs
        transactions = [
            Transaction(
                id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                provenance=Provenance.model,
                confidence=1.0,
                needs_review=False,
                amount=float(row["amount"]),
                currency="GBP",
                occurred_at=datetime.combine(row["date"], datetime.min.time()),
                category="other",
                description="fixture",
                normalized_description="fixture",
                is_anomaly=False,
            )
            for _, row in user_hist.iterrows()
        ]

        # Compute current balance as the sum of history
        current_balance = float(user_hist["amount"].sum())
        fake_uid = uuid.uuid4()

        # Forecaster prediction
        forecasts = compute_forecast(fake_uid, transactions, current_balance=current_balance)

        # Align forecasts and expected by date
        fc_by_date = {f.horizon_date: float(f.projected_balance) for f in forecasts}
        exp_by_date = dict(zip(user_exp["date"], user_exp["projected_balance"].astype(float), strict=False))

        common_dates = sorted(set(fc_by_date) & set(exp_by_date))
        if not common_dates:
            continue

        fc_vals = [fc_by_date[d] for d in common_dates]
        exp_vals = [exp_by_date[d] for d in common_dates]

        # Day-of-week baseline: predict using only dow averages
        dow_avg = _day_of_week_baseline(transactions)
        overall_avg = sum(dow_avg.values()) / max(len(dow_avg), 1)
        base_preds: list[float] = []
        balance = current_balance
        for d in common_dates:
            daily = dow_avg.get(d.weekday() if isinstance(d, date) else d.weekday(), overall_avg)
            balance += daily
            base_preds.append(balance)

        fc_mae = sum(abs(p - e) for p, e in zip(fc_vals, exp_vals, strict=True)) / len(fc_vals)
        base_mae = sum(abs(p - e) for p, e in zip(base_preds, exp_vals, strict=True)) / len(base_preds)
        forecaster_maes.append(fc_mae)
        baseline_maes.append(base_mae)

    assert forecaster_maes, "No forecaster results — check fixture alignment"
    avg_fc_mae = sum(forecaster_maes) / len(forecaster_maes)
    avg_base_mae = sum(baseline_maes) / len(baseline_maes)

    assert avg_fc_mae <= avg_base_mae, (
        f"Forecaster MAE {avg_fc_mae:.4f} exceeds day-of-week baseline MAE {avg_base_mae:.4f}. "
        "Check the forecasting algorithm or regenerate the fixture."
    )
