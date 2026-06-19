"""Slack webhook sender: ops signals ONLY — never user-level transaction data (constitution Art. II).

URL resolved from Vault (via settings.slack_webhook_url). Three payload types:
drift_alarm, retrain_result, anomaly_rate_summary. Timeout + tenacity retry; 4xx not
retried. Non-blocking: failures are logged, not raised (SC-007, FR-021/023).
"""

from __future__ import annotations

import structlog

log = structlog.get_logger(__name__)

_TIMEOUT = 10.0
_MAX_RETRIES = 3


# ── Payload builders (ops-only, no user data) ────────────────────────────────

def build_drift_alarm_payload(
    *,
    signal_name: str,
    metric_value: float,
    threshold: float,
    fired: bool,
) -> dict:
    """Build a drift alarm payload (ops aggregates only — Art. II)."""
    return {
        "type": "drift_alarm",
        "signal_name": signal_name,
        "metric_value": round(metric_value, 4),
        "threshold": round(threshold, 4),
        "fired": fired,
    }


def build_retrain_result_payload(
    *,
    retrain_run_id: str,
    trigger_reason: str,
    gate_verdict: str,
    champion_macro_f1: float,
    challenger_macro_f1: float,
    status: str = "completed",
) -> dict:
    """Build a retrain result payload (run-level aggregates — no user data)."""
    return {
        "type": "retrain_result",
        "retrain_run_id": retrain_run_id,
        "trigger_reason": trigger_reason,
        "gate_verdict": gate_verdict,
        "champion_macro_f1": round(champion_macro_f1, 4),
        "challenger_macro_f1": round(challenger_macro_f1, 4),
        "status": status,
    }


def build_anomaly_rate_payload(
    *,
    anomaly_count: int,
    anomaly_rate: float,
    period_days: int,
) -> dict:
    """Build an anomaly rate summary payload (population aggregate — no user data)."""
    return {
        "type": "anomaly_rate_summary",
        "anomaly_count": anomaly_count,
        "anomaly_rate": round(anomaly_rate, 4),
        "period_days": period_days,
    }


# ── Delivery ─────────────────────────────────────────────────────────────────

def send_slack(payload: dict) -> None:
    """Post a payload to the Vault-sourced Slack webhook URL.

    Non-blocking: transport failures are logged and swallowed (SC-007).
    4xx responses are not retried. Timeout + backoff on 5xx/transport errors.
    """
    from app.core.config import get_settings

    settings = get_settings()
    webhook_url = settings.slack_webhook_url
    if not webhook_url:
        log.info("slack.webhook.no_url", reason="slack_webhook_url not configured")
        return

    try:
        _send_with_retry(webhook_url, payload)
    except Exception as exc:
        # Swallow — a Slack outage must never block or fail any caller (SC-007)
        log.warning("slack.send.failed_swallowed", error=str(exc), payload_type=payload.get("type"))


def _send_with_retry(url: str, payload: dict) -> None:
    """Send the payload with tenacity backoff; 4xx not retried."""
    import httpx
    import tenacity

    @tenacity.retry(
        stop=tenacity.stop_after_attempt(_MAX_RETRIES),
        wait=tenacity.wait_exponential(multiplier=1, min=1, max=10),
        retry=tenacity.retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
        reraise=True,
    )
    def _post() -> None:
        with httpx.Client(timeout=_TIMEOUT) as client:
            response = client.post(url, json=payload)
            if response.status_code >= 400:
                log.warning("slack.send.4xx", status=response.status_code)
                return  # 4xx: do not retry
            response.raise_for_status()
        log.info("slack.send.ok", payload_type=payload.get("type"))

    _post()


async def send_slack_async(payload: dict) -> None:
    """Async variant for use from async worker paths."""
    import httpx

    from app.core.config import get_settings

    settings = get_settings()
    webhook_url = settings.slack_webhook_url
    if not webhook_url:
        log.info("slack.webhook.no_url")
        return

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post(webhook_url, json=payload)
            if response.status_code >= 400:
                log.warning("slack.send.4xx", status=response.status_code)
                return
            log.info("slack.send.ok", payload_type=payload.get("type"))
    except Exception as exc:
        log.warning("slack.send.failed_swallowed", error=str(exc), payload_type=payload.get("type"))
