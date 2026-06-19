"""Generate synthetic forecasting fixtures for CI gate #2.

Run once locally; commit the .parquet outputs.
Usage: python backend/tests/golden/forecasting/generate_fixture.py

The fixture uses SPENDING-ONLY data (no large income spikes) so Prophet's weekly
seasonality modelling can be evaluated cleanly against the day-of-week baseline.
The expected_horizon contains actual future ground-truth values (continuation of
the synthetic generator), NOT baseline predictions.
"""

from __future__ import annotations

import math
import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

_SEED = 42
_N_USERS = 5
_HISTORY_DAYS = 180
_HORIZON_DAYS = 30
_TOTAL_DAYS = _HISTORY_DAYS + _HORIZON_DAYS
_OUT = Path(__file__).parent

random.seed(_SEED)


def _gen_user(user_id: int, n_days: int = _TOTAL_DAYS) -> list[dict]:
    """Produce n_days of synthetic daily spending for one user (spending only).

    Spending-only data lets Prophet's weekly seasonality be evaluated cleanly
    without large income spikes that would dominate the cumulative balance error.
    """
    rows = []
    start = date(2026, 1, 1)
    for d in range(n_days):
        cur = start + timedelta(days=d)
        # Daily spend: weekly pattern + monthly pattern + noise
        daily_spend = (
            -15
            - 5 * math.sin(2 * math.pi * d / 7)          # weekly rhythm
            - 3 * math.sin(2 * math.pi * d / 30)          # monthly rhythm
            + random.gauss(0, 2)
        )
        rows.append({"user_id": user_id, "date": cur, "amount": round(daily_spend, 2)})
    return rows


if __name__ == "__main__":
    all_history: list[dict] = []
    all_expected: list[dict] = []

    for uid in range(_N_USERS):
        all_rows = _gen_user(uid, n_days=_TOTAL_DAYS)
        all_df = pd.DataFrame(all_rows)
        all_df["date"] = pd.to_datetime(all_df["date"]).dt.date

        start_date = all_df["date"].min()
        cutoff = start_date + timedelta(days=_HISTORY_DAYS)

        history_df = all_df[all_df["date"] < cutoff].copy()
        future_df = all_df[all_df["date"] >= cutoff].copy()

        for r in history_df.to_dict("records"):
            all_history.append(r)

        # Expected horizon: actual cumulative balance (ground-truth future)
        history_balance = float(history_df["amount"].sum())
        balance = history_balance
        for _, row in future_df.sort_values("date").iterrows():
            balance += float(row["amount"])
            all_expected.append({
                "date": row["date"],
                "projected_balance": round(balance, 4),
                "user_id": uid,
            })

    history_out = pd.DataFrame(all_history)
    expected_out = pd.DataFrame(all_expected)

    history_out.to_parquet(_OUT / "history.parquet", index=False)
    expected_out.to_parquet(_OUT / "expected_horizon.parquet", index=False)

    print(f"Written {len(history_out)} history rows and {len(expected_out)} expected rows.")
    print("Expected horizon is ground-truth future data (spending-only, no salary spikes).")
