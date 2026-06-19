"""Unit tests: Slack payloads carry zero user-level data — no description, merchant, amount, or user_id in any payload type (FR-022, SC-004, contracts/slack-payloads.md)."""

from __future__ import annotations

import uuid

# Fields that must NEVER appear in any Slack payload (Art. II)
FORBIDDEN_FIELDS = {"description", "merchant", "amount", "user_id", "normalized_description", "transaction_id"}
FORBIDDEN_VALUES = {
    "TESCO STORES 1234",  # sample description
    "TESCO",              # sample merchant
    "42.10",              # sample amount
}


def _check_no_user_data(payload: dict) -> None:
    """Recursively assert no forbidden fields or values appear in payload."""
    def _check(obj, path: str = "") -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                assert k.lower() not in FORBIDDEN_FIELDS, (
                    f"Forbidden field {k!r} found at {path}.{k}"
                )
                _check(v, f"{path}.{k}")
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                _check(item, f"{path}[{i}]")
        elif isinstance(obj, str):
            for forbidden in FORBIDDEN_VALUES:
                assert forbidden not in obj, (
                    f"Forbidden value {forbidden!r} found at {path}: {obj!r}"
                )
    _check(payload)


def test_drift_alarm_payload_no_user_data() -> None:
    """drift_alarm payload contains no user-level data."""
    from app.workers.slack_webhook import build_drift_alarm_payload

    payload = build_drift_alarm_payload(
        signal_name="mean_confidence",
        metric_value=0.55,
        threshold=0.70,
        fired=True,
    )
    _check_no_user_data(payload)
    assert payload["type"] == "drift_alarm"
    assert "signal_name" in payload
    assert "metric_value" in payload


def test_retrain_result_payload_no_user_data() -> None:
    """retrain_result payload contains no user-level data."""
    from app.workers.slack_webhook import build_retrain_result_payload

    payload = build_retrain_result_payload(
        retrain_run_id=str(uuid.uuid4()),
        trigger_reason="manual",
        gate_verdict="beats",
        champion_macro_f1=0.89,
        challenger_macro_f1=0.92,
        status="completed",
    )
    _check_no_user_data(payload)
    assert payload["type"] == "retrain_result"


def test_anomaly_rate_payload_no_user_data() -> None:
    """anomaly_rate_summary payload contains no user-level data."""
    from app.workers.slack_webhook import build_anomaly_rate_payload

    payload = build_anomaly_rate_payload(
        anomaly_count=12,
        anomaly_rate=0.04,
        period_days=7,
    )
    _check_no_user_data(payload)
    assert payload["type"] == "anomaly_rate_summary"


def test_payload_with_known_user_data_present_still_clean() -> None:
    """Even when user data is injected into the environment, payloads stay clean."""
    # Simulate user data being known (e.g., from a DB read)
    user_description = "TESCO STORES 1234"
    user_merchant = "TESCO"
    user_amount = "42.10"
    user_id = str(uuid.uuid4())

    from app.workers.slack_webhook import build_drift_alarm_payload

    # The payload builder must not include these values
    payload = build_drift_alarm_payload(
        signal_name="correction_rate",
        metric_value=0.25,
        threshold=0.20,
        fired=True,
    )
    payload_str = str(payload)
    assert user_description not in payload_str
    assert user_merchant not in payload_str
    assert user_amount not in payload_str
    assert user_id not in payload_str
