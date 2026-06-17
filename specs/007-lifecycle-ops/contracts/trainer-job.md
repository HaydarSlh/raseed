# Trainer Job Contract — RQ `training` queue

The trainer is the single heavy image (torch + transformers), built/run only under the
`training` compose profile, consuming the `training` RQ queue. It is never on a request
path (Art. III). Enqueued by `services/lifecycle/trigger.py` via
`infra/queue.enqueue_retrain()`.

---

## Job input

```json
{
  "retrain_run_id": "uuid",
  "idempotency_key": "string",
  "trigger_reason": "correction_count | time_cooldown | manual | drift",
  "demo_mode": false
}
```
- The worker **refuses a duplicate `idempotency_key`** (a `retrain_runs` row already in a
  terminal state for that key) — at most one job per cooldown window (R6, FR-009).

## Job steps

1. **Load eligible labels**: select `corrections.confirmed_by_human=true` joined to their
   transaction text since the last completed retrain. If count < threshold (prod 100 /
   demo 10) → set `retrain_runs.status='skipped'`, `skipped_reason='insufficient_labels'`,
   stop (FR-012). No model produced.
2. **Partial-unfreeze retrain** (R1): seed from the current champion's base weights, train
   top-N layers + head on CPU, temperature-calibrate on val.
3. **Export artifact** (R3): ONNX + `tokenizer.json` + `model_card.json`; compute SHA-256;
   upload to MinIO `categorizer/<sha256>/…`.
4. **Gate** (R9): score challenger vs champion on the **frozen holdout** (reuse
   `gate_holdout` logic). Record `champion_macro_f1`, `challenger_macro_f1`, `gate_verdict`
   (strict beat; tie = `does_not_beat`).
5. **Register**: insert a `model_registry` row `status='challenger'` with `artifact_uri`,
   `sha256`, `metrics`, `model_card`, `retrain_run_id`. Update `retrain_runs.status=
   'completed'`, link `challenger_id`.
6. **Notify**: enqueue a Slack `retrain_result` payload (contracts/slack-payloads.md).

## Job output (side effects)

- One MinIO artifact set under `categorizer/<sha256>/`.
- One `model_registry` challenger row (or none if skipped/failed).
- One terminal `retrain_runs` row.
- One Slack `retrain_result` alert (aggregates only).
- **No promotion** — promotion is a separate operator-only action (FR-015/016).

## Failure handling
- Any exception → `retrain_runs.status='failed'`, no registry row, no champion change,
  Slack `retrain_result` with `status=failed`. The champion continues serving unchanged.
