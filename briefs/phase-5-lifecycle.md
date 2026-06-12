# Phase 5 — The ML lifecycle & ops

## Intent
User corrections flow into a gated, human-approved retraining loop with drift
detection — visible on an ops page and alerting to Slack.

## In scope (deliverables)
- Review queue UI for `needs_review` rows; user setting: manual review vs
  automatic LLM relabel (Flash-Lite). LLM relabels update the row
  (provenance=llm) but are QUARANTINED from training in a reviewable list;
  human confirmation upgrades provenance to human.
- Corrections store; retrain trigger: 100 corrections OR 14 days (cooldown),
  manual button, demo threshold 10.
- Trainer service (heavy image, torch, compose profile `training`, RQ queue
  `training`, idempotency key): partial-unfreeze retrain on accumulated
  human-confirmed labels, sized for CPU; exports new ONNX + model card + SHA
  to MinIO.
- Champion/challenger gate on the frozen holdout; `model_registry` table
  (artifact URI, SHA, metrics, status); HIL promotion from the ops page
  (operator-only via `is_operator` flag); model-server reload on promote.
- Drift monitor on the light worker: mean confidence + correction rate
  (primary), PSI on category distribution + new-merchant rate (secondary);
  `scripts/simulate_drift.py` injects a skewed held-out-merchant batch.
- Ops page: confidence/correction charts with thresholds, drift status, retrain
  history with champion-vs-challenger numbers, retrain/promote buttons.
- SLACK webhook (incoming-webhook URL resolved from Vault): drift alarms,
  retrain results, aggregate anomaly-rate stats. Timeout, retry/backoff,
  structured logging, never blocking a user-facing response.

## Out of scope
Rails content, red-teaming, erasure (Phase 6).

## Acceptance criteria
- Full loop demonstrable end-to-end: correct 10 rows -> trigger -> retrain ->
  gate -> operator promotes -> new model serving.
- CI gate #7: simulated drift fires the alarm and enqueues a retrain (CI runs
  with the `training` profile enabled so the path is genuinely tested).
- A test proves webhook payloads contain zero user-level transaction data.

## Notes for /plan
Initial foundation training stays in Colab (Phase 2); in-stack retrains are
partial-unfreeze on CPU — never full fine-tunes. Document the lean-serving
rule interpretation (trainer = the one heavy, non-request-path image) in
DECISIONS.md.
