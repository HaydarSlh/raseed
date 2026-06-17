# Quickstart & Validation — The ML Lifecycle & Ops

Runnable scenarios that prove the phase end to end. Detailed shapes live in
[contracts/](./contracts/) and [data-model.md](./data-model.md); this is the run guide.

## Prerequisites

- Phase 0–4 stack healthy: `docker compose up -d` (postgres, redis, minio, vault,
  backend, modelserver, worker, frontend).
- Migrations applied: `cd backend && alembic upgrade head` (through `0005_lifecycle_ops`).
- A seeded operator: a user with `is_operator=true` (set via DB/seed).
- A signed-in normal user with some `needs_review` transactions (upload a statement with
  low-confidence rows, or run the demo seed).
- Demo thresholds active (`demo_mode`): retrain trigger at **10** confirmed corrections.

## Scenario 1 — Review queue → human corrections (US1)

1. Sign in as the normal user; open **Review**. Confirm only your own `needs_review` rows
   appear (`GET /review/queue`).
2. Correct 10 rows (`POST /review/confirm`). Verify each becomes a `corrections` row with
   `provenance=human, confirmed_by_human=true` and leaves `needs_review`.
   **Expected**: 10 human-confirmed corrections; SC-002 (only human rows train) holds.

## Scenario 2 — LLM relabel quarantine (US1)

1. Set review mode to `auto_relabel` (`PUT /settings/review-mode`).
2. Confirm flagged rows are relabeled `provenance=llm, quarantined=true` and shown as
   "awaiting confirmation" — and that they are **absent** from any training-label query.
3. Confirm one quarantined row; verify it upgrades to `provenance=human, quarantined=false`.
   **Expected**: quarantined LLM labels never train until the owning user confirms (FR-005/006).

## Scenario 3 — Trigger → trainer → gate → registry (US2)

1. As operator, press **Retrain** (`POST /ops/retrain`) — or let the 10-correction count
   trip it. Verify exactly one `retrain_runs` row is `enqueued` (a second press in-window
   returns the same run; `force=true` overrides — SC-006).
2. Run the trainer: `docker compose --profile training up trainer` (consumes the
   `training` queue).
   **Expected**: a new ONNX + model card + SHA in MinIO `categorizer/<sha>/`; a
   `model_registry` `challenger` row; `retrain_runs` `completed` with
   champion-vs-challenger macro-F1 and a `gate_verdict`.

## Scenario 4 — Operator promotion → serving reload (US2)

1. As operator, view **Ops** → promotable challengers (`GET /ops/models`).
2. Try to promote as a non-operator → **403** (SC-008). As the operator, promote the
   winning challenger (`POST /ops/promote`).
   **Expected**: registry swaps champion↔archived; model-server `/reload` returns the new
   SHA; `/healthz` reports the new `sha256`; a tie or losing challenger cannot be promoted
   (409, SC-005). A reload SHA mismatch aborts the swap and keeps the prior champion.
3. Confirm the full loop matches **SC-001** (correct 10 → trigger → retrain → gate →
   promote → serving the new model) in one session.

## Scenario 5 — Drift simulation → alarm → Slack → retrain (US3, CI Gate #7)

1. Run `python backend/scripts/simulate_drift.py` (injects the committed skewed
   held-out-merchant batch, isolated from real data).
2. The drift monitor evaluates on-demand: unfamiliar merchants drive **mean confidence**
   below threshold (primary).
   **Expected**: a `drift_signals` row with `fired=true, triggered_retrain=true`; a Slack
   `drift_alarm` sent; a `retrain_runs` row with `trigger_reason=drift` enqueued.
3. **CI Gate #7** (`pytest backend/tests/test_drift_gate.py`): runs the same path
   stack-independently on the fixture with a fake queue/transport — asserts primary signal
   crosses, alert sent, retrain enqueued. (Reconciliation: R5.)

## Scenario 6 — Slack payloads carry zero user data (US3, SC-004)

1. `pytest backend/tests/unit/test_slack_payload.py` — with known user transaction data
   present, build every payload type (drift / retrain / anomaly-rate) and assert none
   contains a description, merchant, amount, or user id.
   **Expected**: green; no forbidden field appears in any payload.

## Scenario 7 — Ops dashboard (US4)

1. As operator, open **Ops**: confidence + correction-rate charts with threshold lines,
   current drift status, retrain history with champion-vs-challenger numbers, and the
   retrain + promote buttons.
2. As a non-operator, confirm Ops and its controls are inaccessible (SC-008).

## CI gates touched

- **Gate #7 — drift fire** (`eval_thresholds.yaml: drift.must_fire_on_simulated_drift: true`):
  stack-independent fixture test (R5).
- Existing **Gate #1** (categorizer holdout) logic is reused by the champion/challenger
  gate (R9) — the frozen holdout stays untouched by anything else.

## Acceptance checklist (maps to spec Success Criteria)

- [ ] SC-001 full loop in one session (Scenarios 1,3,4)
- [ ] SC-002 only human-confirmed labels train (Scenarios 1,2)
- [ ] SC-003 simulated drift fires + enqueues (Scenario 5)
- [ ] SC-004 zero user data in Slack payloads (Scenario 6)
- [ ] SC-005 promote only on beats-champion + operator (Scenario 4)
- [ ] SC-006 one retrain per window (Scenario 3)
- [ ] SC-007 Slack outage never blocks a request (worker-side delivery; inspect logs)
- [ ] SC-008 non-operator cannot reach ops/retrain/promote (Scenarios 4,7)
