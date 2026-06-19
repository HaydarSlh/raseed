"""Analytics computation: forecast (Prophet + day-of-week cold-start), anomaly detection
(robust z-score / IQR + duplicate-charge rule), and recurring-charge detector.

All heavy computation runs in the light worker — never in the lean model-server image
and never on the request path (constitution Art. III + Art. V)."""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from app.domain.analytics import Anomaly, AnomalyType, Cadence, Forecast, Subscription
from app.domain.transaction import Transaction

# ─── Constants ────────────────────────────────────────────────────────────────
_FORECAST_HORIZON_DAYS = 30
_COLD_START_THRESHOLD_DAYS = 30
_IQR_ANOMALY_MULTIPLIER = 2.5
_DUPLICATE_WINDOW_DAYS = 2
_MIN_RECURRING_OCCURRENCES = 3


# ─── Anomaly detection ────────────────────────────────────────────────────────

def _iqr_bounds(values: list[float]) -> tuple[float, float]:
    """Return (lower, upper) bounds using Q1/Q3 + IQR * multiplier."""
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    q1 = sorted_vals[n // 4]
    q3 = sorted_vals[(3 * n) // 4]
    iqr = q3 - q1
    return (q1 - _IQR_ANOMALY_MULTIPLIER * iqr, q3 + _IQR_ANOMALY_MULTIPLIER * iqr)


def detect_anomalies(
    user_id: uuid.UUID, transactions: list[Transaction]
) -> tuple[list[Anomaly], set[uuid.UUID]]:
    """Return (Anomaly rows, set of anomalous transaction ids).

    Two passes:
    1. Robust IQR outlier per category — flags statistical outliers.
    2. Duplicate-charge rule — same merchant + amount within _DUPLICATE_WINDOW_DAYS.
    """
    anomalies: list[Anomaly] = []
    anomalous_ids: set[uuid.UUID] = set()

    # Pass 1: IQR per category
    by_category: dict[str, list[Transaction]] = defaultdict(list)
    for txn in transactions:
        if txn.category and txn.amount is not None:
            by_category[txn.category].append(txn)

    for category, group in by_category.items():
        if len(group) < 5:
            continue
        amounts = [float(t.amount) for t in group]  # type: ignore[arg-type]
        lower, upper = _iqr_bounds(amounts)
        for txn in group:
            val = float(txn.amount)  # type: ignore[arg-type]
            if val < lower or val > upper:
                anomalous_ids.add(txn.id)
                anomalies.append(
                    Anomaly(
                        user_id=user_id,
                        transaction_id=txn.id,
                        anomaly_type=AnomalyType.statistical_outlier,
                        score=round(abs(val - (lower + upper) / 2) / max((upper - lower) / 2, 1e-9), 4),
                        reason=f"Amount {val:.2f} is outside the expected range [{lower:.2f}, {upper:.2f}] for category '{category}'",
                    )
                )

    # Pass 2: duplicate-charge rule — same merchant + amount within window
    by_merchant: dict[str, list[Transaction]] = defaultdict(list)
    for txn in transactions:
        if txn.merchant and txn.amount is not None:
            by_merchant[txn.merchant].append(txn)

    for merchant, group in by_merchant.items():
        sorted_group = sorted(group, key=lambda t: t.occurred_at or datetime.min)
        for i, txn in enumerate(sorted_group):
            for j in range(i + 1, len(sorted_group)):
                other = sorted_group[j]
                if txn.amount != other.amount:
                    continue
                if txn.occurred_at is None or other.occurred_at is None:
                    continue
                delta = abs((other.occurred_at - txn.occurred_at).days)
                if delta <= _DUPLICATE_WINDOW_DAYS:
                    for dup in (txn, other):
                        anomalous_ids.add(dup.id)
                        anomalies.append(
                            Anomaly(
                                user_id=user_id,
                                transaction_id=dup.id,
                                anomaly_type=AnomalyType.duplicate_charge,
                                score=None,
                                reason=f"Possible duplicate charge: {merchant} £{float(txn.amount or 0):.2f} within {delta} day(s)",
                            )
                        )

    return anomalies, anomalous_ids


# ─── Recurring-charge detector ────────────────────────────────────────────────

_CADENCE_MAP: list[tuple[int, Cadence]] = [
    (7, Cadence.weekly),
    (14, Cadence.biweekly),
    (30, Cadence.monthly),
    (90, Cadence.quarterly),
    (365, Cadence.annual),
]


def _best_cadence(deltas_days: list[int]) -> Cadence:
    avg = sum(deltas_days) / len(deltas_days)
    best, best_dist = Cadence.irregular, float("inf")
    for days, cadence in _CADENCE_MAP:
        dist = abs(avg - days)
        if dist < best_dist:
            best_dist, best = dist, cadence
    return best if best_dist < 5 else Cadence.irregular


def detect_subscriptions(user_id: uuid.UUID, transactions: list[Transaction]) -> list[Subscription]:
    """Detect recurring charges by merchant; flag price increases."""
    by_merchant: dict[str, list[Transaction]] = defaultdict(list)
    for txn in transactions:
        if txn.merchant and txn.amount is not None and float(txn.amount) < 0:
            by_merchant[txn.merchant].append(txn)

    subscriptions: list[Subscription] = []
    for merchant, group in by_merchant.items():
        if len(group) < _MIN_RECURRING_OCCURRENCES:
            continue
        sorted_group = sorted(group, key=lambda t: t.occurred_at or datetime.min)
        deltas = []
        for i in range(1, len(sorted_group)):
            ts_curr = sorted_group[i].occurred_at
            ts_prev = sorted_group[i - 1].occurred_at
            if ts_curr and ts_prev:
                deltas.append(abs((ts_curr - ts_prev).days))
        if not deltas:
            continue
        cadence = _best_cadence(deltas)
        if cadence == Cadence.irregular:
            continue

        amounts = [abs(float(t.amount)) for t in sorted_group]  # type: ignore[arg-type]
        typical = sorted(amounts)[len(amounts) // 2]  # median
        last_amount = amounts[-1]
        price_increase = last_amount > typical * 1.05

        avg_delta = sum(deltas) / len(deltas)
        last_date = sorted_group[-1].occurred_at
        next_charge: date | None = None
        if last_date:
            next_charge = (last_date + timedelta(days=int(avg_delta))).date()

        subscriptions.append(
            Subscription(
                user_id=user_id,
                merchant=merchant,
                cadence=cadence,
                typical_amount=Decimal(str(round(typical, 4))),
                last_amount=Decimal(str(round(last_amount, 4))),
                next_charge_date=next_charge,
                price_increase=price_increase,
            )
        )

    return subscriptions


# ─── Forecaster ───────────────────────────────────────────────────────────────

def _day_of_week_baseline(transactions: list[Transaction]) -> dict[int, float]:
    """Mean daily spend by day-of-week for cold-start / gate comparison."""
    by_dow: dict[int, list[float]] = defaultdict(list)
    for txn in transactions:
        if txn.occurred_at and txn.amount is not None:
            dow = txn.occurred_at.weekday()
            by_dow[dow].append(float(txn.amount))
    return {dow: sum(v) / len(v) for dow, v in by_dow.items()}


def compute_forecast(
    user_id: uuid.UUID,
    transactions: list[Transaction],
    current_balance: float = 0.0,
) -> list[Forecast]:
    """Compute a 30-day balance forecast.

    If history < 30 days: cold-start (day-of-week averages).
    Otherwise: attempt Prophet; fall back to cold-start on import error
    (Prophet is an optional heavy dep not available in all envs).
    """
    if not transactions:
        return _cold_start_forecast(user_id, {}, current_balance)

    earliest = min((t.occurred_at for t in transactions if t.occurred_at), default=None)
    if earliest is None:
        return _cold_start_forecast(user_id, {}, current_balance)

    # Handle both tz-aware and tz-naive occurred_at values from different call sites
    now = datetime.now(UTC)
    earliest_aware = earliest if earliest.tzinfo is not None else earliest.replace(tzinfo=UTC)
    history_days = (now - earliest_aware).days
    dow_avg = _day_of_week_baseline(transactions)

    if history_days < _COLD_START_THRESHOLD_DAYS:
        return _cold_start_forecast(user_id, dow_avg, current_balance, is_cold_start=True)

    try:
        return _prophet_forecast(user_id, transactions, dow_avg, current_balance)
    except Exception:
        return _cold_start_forecast(user_id, dow_avg, current_balance, is_cold_start=True)


def _cold_start_forecast(
    user_id: uuid.UUID,
    dow_avg: dict[int, float],
    current_balance: float,
    is_cold_start: bool = True,
) -> list[Forecast]:
    today = date.today()
    overall_avg = sum(dow_avg.values()) / max(len(dow_avg), 1) if dow_avg else -5.0
    forecasts: list[Forecast] = []
    balance = current_balance
    for i in range(1, _FORECAST_HORIZON_DAYS + 1):
        horizon = today + timedelta(days=i)
        daily = dow_avg.get(horizon.weekday(), overall_avg)
        balance += daily
        forecasts.append(
            Forecast(
                user_id=user_id,
                horizon_date=horizon,
                projected_balance=round(balance, 4),
                lower_bound=round(balance * 0.85, 4),
                upper_bound=round(balance * 1.15, 4),
                is_cold_start=is_cold_start,
            )
        )
    return forecasts


def _prophet_forecast(
    user_id: uuid.UUID,
    transactions: list[Transaction],
    dow_avg: dict[int, float],
    current_balance: float,
) -> list[Forecast]:
    import pandas as pd
    from prophet import Prophet  # noqa: PLC0415

    records = [
        {"ds": t.occurred_at.date(), "y": float(t.amount or 0)}
        for t in transactions
        if t.occurred_at and t.amount is not None
    ]
    df = pd.DataFrame(records).groupby("ds")["y"].sum().reset_index()
    df.columns = ["ds", "y"]

    model = Prophet(growth="flat", daily_seasonality=False, yearly_seasonality=False, weekly_seasonality=True)
    model.fit(df)

    future = model.make_future_dataframe(periods=_FORECAST_HORIZON_DAYS)
    forecast_df = model.predict(future)
    horizon_rows = forecast_df.tail(_FORECAST_HORIZON_DAYS)

    balance = current_balance
    forecasts: list[Forecast] = []
    for _, row in horizon_rows.iterrows():
        balance += float(row["yhat"])
        forecasts.append(
            Forecast(
                user_id=user_id,
                horizon_date=row["ds"].date(),
                projected_balance=round(balance, 4),
                lower_bound=round(balance + float(row["yhat_lower"]) - float(row["yhat"]), 4),
                upper_bound=round(balance + float(row["yhat_upper"]) - float(row["yhat"]), 4),
                is_cold_start=False,
            )
        )
    return forecasts
