"""Drift detection job: primary (confidence, correction rate → retrain) and secondary (PSI, new-merchant rate → alarm only). Runs daily + on-demand (constitution Art. III/V, FR-018/019)."""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

log = structlog.get_logger(__name__)


# ── Pure math helpers (testable without DB) ──────────────────────────────────

def compute_psi(current_hist: dict[str, float], reference_hist: dict[str, float]) -> float:
    """Population Stability Index between current and reference category distributions.

    PSI = Σ (P_i - Q_i) * ln(P_i / Q_i)
    Values < 0.10: no shift; 0.10–0.20: moderate; > 0.20: significant.
    """
    categories = set(current_hist) | set(reference_hist)
    psi = 0.0
    for cat in categories:
        p = current_hist.get(cat, 0.0001)
        q = reference_hist.get(cat, 0.0001)
        # Guard against zero to avoid log(0)
        p = max(p, 0.0001)
        q = max(q, 0.0001)
        psi += (p - q) * math.log(p / q)
    return abs(psi)


def compute_new_merchant_rate(
    window_merchants: set[str],
    training_merchants: set[str],
) -> float:
    """Share of window merchants that were unseen in the training set."""
    if not window_merchants:
        return 0.0
    new_count = len(window_merchants - training_merchants)
    return new_count / len(window_merchants)


def compute_drift_signals(
    *,
    mean_confidence: float,
    correction_rate: float,
    psi: float,
    new_merchant_rate: float,
    category_histogram: dict[str, float],
    training_histogram: dict[str, float],
    seen_merchants: set[str],
    window_merchants: set[str],
    settings: Any,
) -> dict:
    """Compute drift signal outcomes without any I/O.

    Returns:
        dict with keys: fired, fired_signals, triggered_retrain
    """
    fired_signals: list[str] = []

    # Primary signals (→ retrain when fired)
    primary_fired = False
    if mean_confidence < settings.drift_mean_confidence_min:
        fired_signals.append("mean_confidence")
        primary_fired = True
    if correction_rate > settings.drift_correction_rate_max:
        fired_signals.append("correction_rate")
        primary_fired = True

    # Secondary signals (→ alarm + Slack only, never retrain)
    if psi > settings.drift_psi_max:
        fired_signals.append("psi")
    if new_merchant_rate > settings.drift_new_merchant_rate_max:
        fired_signals.append("new_merchant_rate")

    fired = len(fired_signals) > 0
    return {
        "fired": fired,
        "fired_signals": fired_signals,
        "triggered_retrain": primary_fired,
    }


# ── DB-aware runner ───────────────────────────────────────────────────────────

async def run_drift_monitor(
    session: Any,
    *,
    source: str = "scheduled",
    window_days: int = 7,
) -> dict:
    """Evaluate drift signals over the trailing window, persist a DriftSignal row, and fire alerts.

    source: 'scheduled' | 'on_demand' | 'simulation'
    Returns the outcome dict (same shape as compute_drift_signals, + db_id).
    """
    from sqlalchemy import func, select

    from app.core.config import get_settings
    from app.domain.correction import Correction
    from app.domain.drift_signal import DriftSignal, DriftSource
    from app.domain.model_registry import ModelRegistry, ModelStatus
    from app.domain.transaction import Transaction
    from app.infra.minio import load_model_card
    from app.repositories.drift_repo import DriftRepository
    from app.services.lifecycle.trigger import RetrainTriggerService
    from app.workers.slack_webhook import build_drift_alarm_payload, send_slack_async

    settings = get_settings()
    since = datetime.now(UTC) - timedelta(days=window_days)

    # 1. Compute mean confidence over window (privileged, aggregates only)
    conf_result = await session.execute(
        select(func.avg(Transaction.confidence)).where(Transaction.occurred_at > since)
    )
    mean_confidence = float(conf_result.scalar_one() or 0.80)

    # 2. Correction rate over window
    total_result = await session.execute(
        select(func.count()).select_from(Transaction).where(Transaction.occurred_at > since)
    )
    total_txns = int(total_result.scalar_one() or 1)

    corrections_result = await session.execute(
        select(func.count()).select_from(Correction).where(Correction.created_at > since)
    )
    correction_count = int(corrections_result.scalar_one() or 0)
    correction_rate = correction_count / total_txns if total_txns > 0 else 0.0

    # 3. Load drift reference from current champion's model_card (R4/U1)
    champion_result = await session.execute(
        select(ModelRegistry).where(ModelRegistry.status == ModelStatus.champion)
    )
    champion = champion_result.scalar_one_or_none()

    training_histogram: dict[str, float] = {}
    training_merchants: set[str] = set()
    if champion and champion.sha256:
        try:
            model_card = load_model_card(champion.sha256)
            drift_ref = model_card.get("drift_reference", {})
            training_histogram = drift_ref.get("category_histogram", {})
            training_merchants = set(drift_ref.get("training_merchants", []))
        except Exception as exc:
            log.warning("drift.model_card.load_failed", error=str(exc))

    # 4. Compute PSI — current category distribution
    cat_result = await session.execute(
        select(Transaction.category, func.count().label("cnt"))
        .where(Transaction.occurred_at > since)
        .group_by(Transaction.category)
    )
    cat_rows = cat_result.all()
    total_cats = sum(row[1] for row in cat_rows)
    category_histogram = {row[0]: row[1] / total_cats for row in cat_rows if row[0] and total_cats > 0}
    psi = compute_psi(category_histogram, training_histogram)

    # 5. Compute new-merchant rate
    merchant_result = await session.execute(
        select(Transaction.merchant)
        .where(Transaction.occurred_at > since)
        .distinct()
    )
    window_merchants: set[str] = {row[0] for row in merchant_result.all() if row[0]}
    new_merchant_rate = compute_new_merchant_rate(window_merchants, training_merchants)

    # 6. Determine fired signals
    outcome = compute_drift_signals(
        mean_confidence=mean_confidence,
        correction_rate=correction_rate,
        psi=psi,
        new_merchant_rate=new_merchant_rate,
        category_histogram=category_histogram,
        training_histogram=training_histogram,
        seen_merchants=training_merchants,
        window_merchants=window_merchants,
        settings=settings,
    )

    # 7. Persist DriftSignal row
    thresholds_snapshot = {
        "mean_confidence_min": settings.drift_mean_confidence_min,
        "correction_rate_max": settings.drift_correction_rate_max,
        "psi_max": settings.drift_psi_max,
        "new_merchant_rate_max": settings.drift_new_merchant_rate_max,
    }
    signal = DriftSignal(
        mean_confidence=mean_confidence,
        correction_rate=correction_rate,
        psi=psi,
        new_merchant_rate=new_merchant_rate,
        thresholds=thresholds_snapshot,
        fired=outcome["fired"],
        fired_signals=outcome["fired_signals"],
        triggered_retrain=outcome["triggered_retrain"],
        source=DriftSource(source),
    )
    drift_repo = DriftRepository(session)
    signal = await drift_repo.insert(signal)
    await session.commit()

    log.info(
        "drift.evaluated",
        mean_confidence=round(mean_confidence, 4),
        correction_rate=round(correction_rate, 4),
        psi=round(psi, 4),
        fired=outcome["fired"],
        fired_signals=outcome["fired_signals"],
        triggered_retrain=outcome["triggered_retrain"],
        source=source,
    )

    # 8. Slack alerts for fired signals (non-blocking)
    for signal_name in outcome["fired_signals"]:
        metric_val = {
            "mean_confidence": mean_confidence,
            "correction_rate": correction_rate,
            "psi": psi,
            "new_merchant_rate": new_merchant_rate,
        }.get(signal_name, 0.0)
        threshold_val = {
            "mean_confidence": settings.drift_mean_confidence_min,
            "correction_rate": settings.drift_correction_rate_max,
            "psi": settings.drift_psi_max,
            "new_merchant_rate": settings.drift_new_merchant_rate_max,
        }.get(signal_name, 0.0)
        payload = build_drift_alarm_payload(
            signal_name=signal_name,
            metric_value=metric_val,
            threshold=threshold_val,
            fired=True,
        )
        await send_slack_async(payload)

    # 9. Enqueue retrain only on primary signal crossings (FR-019)
    if outcome["triggered_retrain"]:
        trigger_svc = RetrainTriggerService(session)
        await trigger_svc.trigger_drift()

    return {**outcome, "db_id": str(signal.id)}
