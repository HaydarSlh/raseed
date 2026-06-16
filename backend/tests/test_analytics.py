"""Unit tests for anomaly detection and recurring-charge detector (no DB / no Prophet)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from app.domain.analytics import AnomalyType, Cadence
from app.domain.transaction import Provenance, Transaction
from app.services.analytics import detect_anomalies, detect_subscriptions


def _txn(
    *,
    amount: float,
    category: str = "groceries",
    merchant: str | None = None,
    occurred_at: datetime | None = None,
    user_id: uuid.UUID | None = None,
) -> Transaction:
    uid = user_id or uuid.uuid4()
    return Transaction(
        id=uuid.uuid4(),
        user_id=uid,
        provenance=Provenance.model,
        confidence=0.95,
        needs_review=False,
        amount=Decimal(str(amount)),
        currency="GBP",
        merchant=merchant,
        occurred_at=occurred_at or datetime(2026, 6, 1),
        category=category,
        description="test",
        normalized_description="test",
        is_anomaly=False,
    )


class TestAnomalyDetection:
    def test_iqr_outlier_flagged(self):
        user_id = uuid.uuid4()
        normal = [_txn(amount=-10.0, category="groceries", user_id=user_id) for _ in range(20)]
        outlier = _txn(amount=-9999.0, category="groceries", user_id=user_id)
        transactions = normal + [outlier]

        anomalies, anomalous_ids = detect_anomalies(user_id, transactions)

        assert outlier.id in anomalous_ids
        types = {a.anomaly_type for a in anomalies}
        assert AnomalyType.statistical_outlier in types

    def test_small_category_no_flag(self):
        user_id = uuid.uuid4()
        # Only 3 transactions — below the minimum of 5
        transactions = [_txn(amount=-10.0, category="fitness", user_id=user_id) for _ in range(3)]
        transactions.append(_txn(amount=-9999.0, category="fitness", user_id=user_id))

        _, anomalous_ids = detect_anomalies(user_id, transactions)
        assert len(anomalous_ids) == 0

    def test_duplicate_charge_flagged(self):
        user_id = uuid.uuid4()
        t1 = _txn(amount=-9.99, merchant="Netflix", occurred_at=datetime(2026, 6, 1), user_id=user_id)
        t2 = _txn(amount=-9.99, merchant="Netflix", occurred_at=datetime(2026, 6, 2), user_id=user_id)
        other = [_txn(amount=-5.0, category="groceries", user_id=user_id) for _ in range(10)]

        anomalies, anomalous_ids = detect_anomalies(user_id, [t1, t2] + other)

        assert t1.id in anomalous_ids or t2.id in anomalous_ids
        types = {a.anomaly_type for a in anomalies}
        assert AnomalyType.duplicate_charge in types

    def test_no_false_positive_different_amounts(self):
        user_id = uuid.uuid4()
        t1 = _txn(amount=-9.99, merchant="Netflix", occurred_at=datetime(2026, 6, 1), user_id=user_id)
        t2 = _txn(amount=-12.99, merchant="Netflix", occurred_at=datetime(2026, 6, 2), user_id=user_id)

        _, anomalous_ids = detect_anomalies(user_id, [t1, t2])
        # Different amounts -> no duplicate
        assert t1.id not in anomalous_ids or t2.id not in anomalous_ids


class TestSubscriptionDetection:
    def _monthly_sub(self, merchant: str, user_id: uuid.UUID) -> list[Transaction]:

        base = datetime(2026, 1, 1)
        return [
            _txn(amount=-9.99, merchant=merchant, occurred_at=base + __import__("datetime").timedelta(days=30 * i), user_id=user_id)
            for i in range(4)
        ]

    def test_monthly_subscription_detected(self):
        from datetime import timedelta

        user_id = uuid.uuid4()
        base = datetime(2026, 1, 1)
        transactions = [
            _txn(amount=-9.99, merchant="Spotify", occurred_at=base + timedelta(days=30 * i), user_id=user_id)
            for i in range(4)
        ]

        subs = detect_subscriptions(user_id, transactions)

        assert len(subs) == 1
        assert subs[0].merchant == "Spotify"
        assert subs[0].cadence == Cadence.monthly

    def test_insufficient_occurrences_skipped(self):
        user_id = uuid.uuid4()
        from datetime import timedelta

        base = datetime(2026, 1, 1)
        transactions = [
            _txn(amount=-9.99, merchant="Gym", occurred_at=base + timedelta(days=30 * i), user_id=user_id)
            for i in range(2)
        ]

        subs = detect_subscriptions(user_id, transactions)
        assert len(subs) == 0

    def test_price_increase_flagged(self):
        from datetime import timedelta

        user_id = uuid.uuid4()
        base = datetime(2026, 1, 1)
        transactions = [
            _txn(amount=-9.99, merchant="Disney+", occurred_at=base + timedelta(days=30 * i), user_id=user_id)
            for i in range(3)
        ] + [
            _txn(amount=-13.99, merchant="Disney+", occurred_at=base + timedelta(days=90), user_id=user_id)
        ]

        subs = detect_subscriptions(user_id, transactions)
        matching = [s for s in subs if s.merchant == "Disney+"]
        assert matching
        assert matching[0].price_increase is True
