"""Generate synthetic forecasting fixtures for CI gate #2.

Run once locally; commit the .parquet outputs.
Usage: python backend/tests/golden/forecasting/generate_fixture.py
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
_OUT = Path(__file__).parent

random.seed(_SEED)


def _gen_user(user_id: int) -> list[dict]:
    """Produce ~_HISTORY_DAYS of synthetic daily spending for one user."""
    base_income = 2000 + user_id * 200
    rows = []
    start = date(2026, 1, 1)
    for d in range(_HISTORY_DAYS):
        cur = start + timedelta(days=d)
        # Monthly salary on the 1st
        if cur.day == 1:
            rows.append({"user_id": user_id, "date": cur, "amount": base_income})
        # Daily spend: seasonal + weekly + noise
        daily_spend = (
            -15
            - 5 * math.sin(2 * math.pi * d / 7)          # weekly pattern
            - 3 * math.sin(2 * math.pi * d / 30)          # monthly pattern
            + random.gauss(0, 3)
        )
        rows.append({"user_id": user_id, "date": cur, "amount": round(daily_spend, 2)})
    return rows


def _day_of_week_baseline(df: pd.DataFrame) -> dict[int, float]:
    df = df.copy()
    df["dow"] = pd.to_datetime(df["date"]).dt.dayofweek
    return df.groupby("dow")["amount"].mean().to_dict()


def _compute_horizon(df: pd.DataFrame, horizon_days: int = _HORIZON_DAYS) -> pd.DataFrame:
    last_balance = float(df["amount"].sum())
    last_date = pd.to_datetime(df["date"]).max()
    dow_avg = _day_of_week_baseline(df)
    overall_avg = sum(dow_avg.values()) / max(len(dow_avg), 1)
    rows = []
    balance = last_balance
    for i in range(1, horizon_days + 1):
        d = last_date + timedelta(days=i)
        daily = dow_avg.get(d.weekday(), overall_avg)
        balance += daily
        rows.append({"date": d.date(), "projected_balance": round(balance, 4)})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    all_history: list[dict] = []
    all_expected: list[dict] = []

    for uid in range(_N_USERS):
        user_rows = _gen_user(uid)
        for r in user_rows:
            all_history.append(r)

        user_df = pd.DataFrame(user_rows)
        horizon_df = _compute_horizon(user_df)
        horizon_df["user_id"] = uid
        all_expected.append(horizon_df)

    history_df = pd.DataFrame(all_history)
    expected_df = pd.concat(all_expected, ignore_index=True)

    history_df.to_parquet(_OUT / "history.parquet", index=False)
    expected_df.to_parquet(_OUT / "expected_horizon.parquet", index=False)

    print(f"Written {len(history_df)} history rows and {len(expected_df)} expected rows.")
