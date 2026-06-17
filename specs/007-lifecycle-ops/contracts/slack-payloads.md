# Slack Payload Contracts — ops signals ONLY (the no-user-data contract)

Every Slack alert is built from a **frozen allowlist of fields**. No field may contain a
transaction description, merchant name, amount, account, or any user identifier (Art. II,
FR-022). The `test_slack_payload.py` test (SC-004) asserts, for every payload builder,
that the serialized JSON contains none of those — verified by round-tripping a fixture
with known user data present in the DB and confirming it never appears in the payload.

Destination: an incoming-webhook URL resolved from Vault (`slack_webhook_url`), never
hardcoded (FR-021). Delivery: timeout + tenacity backoff (4xx not retried), non-blocking
worker job, failures logged not raised (FR-023).

---

## 1. Drift alarm

```json
{
  "type": "drift_alarm",
  "evaluated_at": "2026-06-17T03:00:00Z",
  "source": "scheduled",
  "fired_signals": [
    { "signal": "mean_confidence", "tier": "primary", "value": 0.61, "threshold": 0.70 }
  ],
  "triggered_retrain": true,
  "retrain_run_id": "uuid-or-null"
}
```
Allowed fields only: signal names, numeric values, thresholds, tier, timestamps, run id.

## 2. Retrain result

```json
{
  "type": "retrain_result",
  "retrain_run_id": "uuid",
  "trigger_reason": "drift",
  "status": "completed",
  "gate_verdict": "beats",
  "champion_macro_f1": 0.8934,
  "challenger_macro_f1": 0.9012,
  "labels_used": 47,
  "awaiting_operator_promotion": true
}
```
`labels_used` is a count, not the labels themselves. No per-transaction data.

## 3. Aggregate anomaly-rate summary

```json
{
  "type": "anomaly_rate_summary",
  "period": "2026-06-10/2026-06-17",
  "anomaly_count": 124,
  "transaction_count": 4210,
  "anomaly_rate": 0.0294,
  "distinct_users_bucket": "100+"
}
```
Counts and rates only; `distinct_users_bucket` is a coarse k-anonymity-style bucket, not
a precise user count, and never a user id.

---

## Forbidden in ALL payloads (asserted by SC-004 test)
- transaction `description`, `normalized_description`, `merchant`
- `amount`, `currency`
- `user_id`, email, any per-user identifier
- raw category labels tied to a specific user's transaction
