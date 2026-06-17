---
description: "Task list for The ML Lifecycle & Ops (Phase 5)"
---

# Tasks: The ML Lifecycle & Ops

**Input**: Design documents from `specs/007-lifecycle-ops/`

**Prerequisites**: plan.md, spec.md, research.md (R1–R10), data-model.md,
contracts/http-api.md, contracts/slack-payloads.md, contracts/trainer-job.md, quickstart.md

**Tests**: INCLUDED — the constitution (Art. V) requires every phase to ship tests, and
the brief makes CI gate #7 (drift-fire) and the Slack no-user-data test acceptance
criteria. All CI tests are stack-independent (committed fixtures, `FakeLLM`, fake RQ
queue/transport); the heavy trainer container is exercised only in the quickstart demo.

**Organization**: Tasks grouped by user story. Backend paths under `backend/`; frontend
under `frontend/`; trainer at `trainer/`; model-server at `modelserver/`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no incomplete dependencies)
- **[Story]**: US1–US4 maps to the spec's user stories

---

## Phase 1: Setup (Shared Infrastructure)

- [X] T001 Add Phase-5 tunables to `backend/app/core/config.py` (Settings): `retrain_threshold_prod: int = 100`, `retrain_threshold_demo: int = 10`, `retrain_cooldown_days: int = 14`, `demo_mode: bool = False`, `slack_webhook_url: str = ""`, and drift thresholds with documented seed defaults: `drift_mean_confidence_min: float = 0.70`, `drift_correction_rate_max: float = 0.20`, `drift_psi_max: float = 0.20`, `drift_new_merchant_rate_max: float = 0.15` (seeds chosen from the Phase-2 holdout confidence distribution; defaults are REQUIRED because `extra='forbid'` fields without a default become mandatory env vars and would block boot). Tune with simulate_drift.py and record each number in DECISIONS (T058).
- [X] T002 [P] Extend `backend/app/infra/vault.py`: add `slack_webhook_url` to `_REQUIRED_SECRETS` (local `.env` fallback documented, refuse-to-boot in non-local on missing).
- [X] T003 [P] Implement `backend/app/infra/minio.py`: a client scoped to the `model-artifacts` bucket with `upload_artifact(sha256, files)` and `download_artifact(sha256)→local paths` using content-addressed keys `categorizer/<sha256>/…` (R3). Never writes user data (Art. II).
- [X] T004 [P] Extend `backend/app/infra/queue.py`: add the `training` queue and `enqueue_retrain(retrain_run_id, idempotency_key, trigger_reason, demo_mode)`; the worker refuses a duplicate idempotency key (R6, contracts/trainer-job.md).
- [X] T005 [P] Update `eval_thresholds.yaml`: set `drift.must_fire_on_simulated_drift: true` (Gate #7) and add a `drift` thresholds block mirroring the T001 config values (with a comment pointing to DECISIONS).

**Checkpoint**: settings load; Vault resolves the Slack URL; MinIO artifact round-trip works; `training` queue enqueues; Gate #7 threshold present.

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: No user-story work begins until this phase is complete.

- [X] T006 Create migration `backend/alembic/versions/0005_lifecycle_ops.py`: extend `corrections` (`provenance` enum llm/human, `quarantined` bool, `confirmed_at` ts); extend `model_registry` (`artifact_uri`, `metrics` JSONB, `retrain_run_id` FK, `promoted_by` FK, `promoted_at`); create `retrain_runs` and `drift_signals` (global ops tables, no user_id, no RLS); create `user_settings` (`user_id` PK, `review_mode` enum default manual, RLS-scoped). Add the `at-most-one-champion` partial unique index. Grant the privileged stats role read on ops tables (data-model.md).
- [X] T007 [P] Extend `backend/app/domain/correction.py`: add `provenance` (reuse `Provenance`, constrained to llm/human in app logic), `quarantined`, `confirmed_at` (data-model).
- [X] T008 [P] Extend `backend/app/domain/model_registry.py`: add `artifact_uri`, `metrics` (JSONB), `retrain_run_id`, `promoted_by`, `promoted_at` (data-model).
- [X] T009 [P] Create `backend/app/domain/retrain_run.py`: `RetrainRun` with `TriggerReason`/`RunStatus` enums, `idempotency_key` UNIQUE, metrics + verdict fields (data-model).
- [X] T010 [P] Create `backend/app/domain/drift_signal.py`: `DriftSignal` snapshot with `fired`, `fired_signals` JSONB, `triggered_retrain`, `source` enum (data-model).
- [X] T011 [P] Create `backend/app/domain/user_settings.py`: `UserSettings` with `ReviewMode` enum (default `manual`).
- [X] T012 [P] Create `backend/app/repositories/corrections_repo.py`: write a correction, list quarantined for a user, and `count_confirmed_since(last_retrain_at)` (FR-007).
- [X] T013 [P] Create `backend/app/repositories/model_registry_repo.py`: champion lookup, list promotable challengers, atomic champion↔archived swap (single-champion invariant).
- [X] T014 [P] Create `backend/app/repositories/retrain_runs_repo.py`: create/update runs, fetch history, idempotency-key guard.
- [X] T015 [P] Create `backend/app/repositories/drift_repo.py`: insert a signal snapshot, fetch the latest + a series for charts.
- [X] T016 [P] Register new domain models so Alembic autogenerate/metadata and app imports see them (e.g. `backend/app/domain/__init__.py` and the model metadata import site).

**Checkpoint**: `alembic upgrade head` applies cleanly; all new models/repos import; single-champion invariant enforced at the DB.

---

## Phase 3: User Story 1 — Review queue & corrections (Priority: P1) 🎯 MVP

**Goal**: A user reviews their `needs_review` rows and confirms/corrects categories
(human provenance); optionally auto-relabel via Flash-Lite into an owning-user-confirmed
quarantine.

**Independent Test**: Flag rows → open the queue → correct 10 → verify 10 human-confirmed
corrections; with auto mode on, verify LLM relabels are quarantined and only the owning
user's confirmation upgrades them.

- [X] T017 [P] [US1] Unit test `backend/tests/unit/test_review_queue.py`: confirming a row writes a correction with `provenance=human, confirmed_by_human=true` and clears `needs_review`; queue is RLS-scoped to the owner.
- [X] T018 [P] [US1] Unit test `backend/tests/unit/test_relabel_quarantine.py`: auto-relabel writes `provenance=llm, quarantined=true`, excluded from the training-label query; only the owning user's confirm upgrades to `human` (FR-005/006).
- [X] T019 [P] [US1] Create `backend/app/schemas/review.py`: review item, confirm request/response, review-mode get/put (contracts/http-api.md).
- [X] T020 [US1] Implement `backend/app/services/review/queue.py`: list the user's `needs_review` + quarantined rows; `confirm(transaction_id, category)` writes the human correction and clears review state (reuses the Phase-4 correction path).
- [X] T021 [US1] Implement `backend/app/services/review/relabel.py`: Flash-Lite auto-relabel (mechanical tier, `infra/llm.py`) writing `provenance=llm, quarantined=true`; runs as a batched worker job, never on the request path (R8).
- [X] T022 [US1] Create `backend/app/api/review.py`: `GET /review/queue`, `POST /review/confirm` (RLS session, user-scoped).
- [X] T023 [US1] Create `backend/app/api/settings.py`: `GET/PUT /settings/review-mode`; switching to `auto_relabel` enqueues the relabel job for existing flagged rows (contracts/http-api.md).
- [X] T024 [US1] Register `review_router` and `settings_router` in `backend/main.py`.
- [X] T025 [P] [US1] Create `frontend/src/api/reviewApi.ts`: review queue + confirm + review-mode client.
- [X] T026 [P] [US1] Create `frontend/src/components/ReviewRow.tsx`: one flagged transaction with a category control + confirm; quarantined rows show "awaiting confirmation".
- [X] T027 [US1] Create `frontend/src/pages/Review.tsx`: the queue page + review-mode toggle; wire route in `frontend/src/App.tsx` and a Review link in `frontend/src/components/NavBar.tsx`.
- [X] T028 [P] [US1] Frontend test `frontend/src/pages/Review.test.tsx`: renders queue rows, confirm calls the API, quarantined rows are labeled.

**Checkpoint**: US1 fully testable on its own — corrections flow into the store; MVP delivers a cleaner user-corrected history.

---

## Phase 4: User Story 2 — Gated retrain + operator promotion (Priority: P2)

**Goal**: Accumulated confirmations (or cooldown/manual/drift) trip one idempotent
retrain; the trainer produces a challenger; the gate scores it on the frozen holdout; an
operator promotes the winner and the model-server reloads.

**Independent Test**: With ≥ demo-threshold confirmations, trigger a retrain → challenger
+ registry entry with champion-vs-challenger numbers → operator promotes → model-server
serves the new artifact; non-operators cannot promote; ties/losers cannot be promoted.

- [X] T029 [P] [US2] Unit test `backend/tests/unit/test_retrain_trigger.py`: count/cooldown/manual/drift fire; one global cooldown ⇒ at most one job/window; manual `force` overrides (FR-009, SC-006).
- [X] T030 [P] [US2] Unit test `backend/tests/unit/test_gate.py`: challenger strictly beats champion ⇒ `beats`; tie ⇒ `does_not_beat` (no promote) (FR-015).
- [X] T031 [P] [US2] Integration test `backend/tests/integration/test_promote_reload.py`: operator promote swaps champion↔archived and calls model-server `/reload`; a SHA mismatch aborts the swap and keeps the prior champion (FR-017).
- [X] T032 [P] [US2] Integration test `backend/tests/integration/test_operator_access.py`: non-operator gets 403 on `/ops/retrain` and `/ops/promote` (FR-016, SC-008).
- [X] T033 [US2] Implement `backend/app/services/lifecycle/trigger.py`: evaluate all sources, hold the global Redis cooldown/idempotency key, create a `retrain_runs` row, and `enqueue_retrain` (R6); manual force bypasses + resets the key.
- [X] T034 [US2] Implement `backend/app/services/lifecycle/gate.py`: orchestrate and expose the gate VERDICT — the heavy scoring (load ONNX, run inference on the frozen holdout, compute macro-F1) runs in the TRAINER (T037, which carries onnxruntime/sklearn/pandas). This service only reads `retrain_runs`/`model_registry` to surface the stored champion-vs-challenger metrics + verdict to the ops/promote paths; it does NOT import sklearn or load the holdout (keeps the backend image lean) (R9).
- [X] T035 [US2] Implement `backend/app/services/lifecycle/promote.py`: operator promotion — verify `gate_verdict='beats'`, registry swap, then `modelserver_client.reload(sha)`; roll back on reload failure (FR-015/017).
- [X] T036 [US2] Extend `backend/app/infra/modelserver_client.py`: add `reload(sha256)` calling the model-server `POST /reload` with timeout + tenacity (4xx not retried).
- [X] T037 [US2] Implement `trainer/train.py` per contracts/trainer-job.md: refuse duplicate idempotency key; load `confirmed_by_human=true` labels (skip with reason if < threshold); partial-unfreeze CPU retrain seeded from champion (R1); export ONNX + model card + SHA to MinIO. The `model_card.json` MUST include the drift reference (training category histogram + normalized-merchant set) for the drift monitor's PSI/new-merchant baseline (R4). Run the gate IN-PROCESS here (reuse `training/gate_holdout.py`: strict beat vs the current champion on the frozen holdout) and persist champion/challenger macro-F1 + verdict to `retrain_runs` — the backend never re-runs scoring. Set the challenger `version` by incrementing the current champion's MINOR (e.g. v2.1.0 → v2.2.0; foundation training owns MAJOR). Insert a `challenger` registry row; mark the run; enqueue a Slack `retrain_result`.
- [X] T038 [P] [US2] Extend `modelserver/categorizer.py`: add a MinIO-by-SHA provider for `get_current_artifact()` (downloads to cache, leaves boot/hash-verify untouched) (R3).
- [X] T039 [US2] Extend `modelserver/app.py`: add `POST /reload` — re-resolve by SHA via the seam, re-verify SHA, atomically swap `app.state.categorizer`; refuse + retain prior on mismatch (R2, contracts/http-api.md).
- [X] T040 [P] [US2] Create `backend/app/schemas/ops.py`: retrain request (`force`), promote request (`model_registry_id`), and their responses (contracts/http-api.md).
- [X] T041 [US2] Create `backend/app/api/ops.py` (action endpoints): `POST /ops/retrain`, `POST /ops/promote`, `GET /ops/models`, all behind an `is_operator` dependency (403 otherwise); register `ops_router` in `backend/main.py`.

**Checkpoint**: the full correct→trigger→retrain→gate→promote→serve loop works (SC-001); promotion is operator-gated and beats-only.

---

## Phase 5: User Story 3 — Drift detection + Slack alerting (Priority: P3)

**Goal**: A daily + on-demand monitor tracks primary (confidence, correction rate →
retrain) and secondary (PSI, new-merchant rate → alarm only) signals, posts ops-only
Slack alerts, and a simulation drives CI gate #7.

**Independent Test**: Run `simulate_drift.py` → primary signal crosses → `drift_signals`
fired+triggered_retrain → Slack alert sent → retrain enqueued; inspect payloads for zero
user data.

- [X] T042 [P] [US3] Add committed fixture `backend/tests/fixtures/drift_skewed_batch.parquet`: a skewed held-out-merchant batch (unfamiliar merchants → low confidence), isolated from real data.
- [X] T043 [P] [US3] Unit test `backend/tests/unit/test_drift_signals.py`: PSI + new-merchant math; primary crossing ⇒ enqueue + alert; secondary-only crossing ⇒ alert, NO retrain (FR-018/019, R4).
- [X] T044 [P] [US3] Unit test `backend/tests/unit/test_slack_payload.py`: every payload type (drift/retrain/anomaly-rate) contains zero user-level data with known user data present in the DB (FR-022, SC-004, contracts/slack-payloads.md).
- [X] T045 [US3] Implement `backend/app/workers/slack_webhook.py`: build the three ops-only payloads, resolve the Vault URL, send with timeout + tenacity backoff (4xx not retried), non-blocking, log-not-raise on failure (R7, FR-021/023). Include a test that a transport timeout/5xx is swallowed-and-logged and never raises into the caller (SC-007: a Slack outage never blocks/fails a user-facing path).
- [X] T046 [US3] Implement `backend/app/workers/drift.py`: compute primary + secondary signals over the window (privileged, aggregates only); load the PSI baseline + new-merchant reference from the current champion's `model_card.json` (R4) and compute PSI vs that histogram + new-merchant rate vs that set; write a `drift_signals` row, fire alarm + Slack, and (primary only, subject to cooldown) call the retrain trigger (FR-018/019).
- [X] T047 [US3] Extend `backend/app/workers/worker.py`: consume the `training` queue and add a daily scheduler tick that invokes the drift monitor (cadence per clarification); keep on-demand invocation available.
- [X] T048 [US3] Create `backend/scripts/simulate_drift.py`: load the committed skewed batch into an isolated evaluation, invoke the monitor on-demand, and print the fired signals + enqueued run (R5, quickstart Scenario 5).
- [X] T049 [US3] Create CI gate test `backend/tests/test_drift_gate.py` (Gate #7): stack-independent — run the drift path on the fixture with a fake queue + fake Slack transport; assert a primary signal crosses, an alert is sent, and `enqueue_retrain` is called (R5).

**Checkpoint**: simulated drift fires the alarm, sends an ops-only alert, and enqueues a retrain; Gate #7 green; SC-003/SC-004/SC-007 satisfied.

---

## Phase 6: User Story 4 — Operator ops dashboard (Priority: P4)

**Goal**: An operator sees confidence/correction charts with thresholds, drift status,
and retrain history with champion-vs-challenger numbers, plus retrain/promote controls.

**Independent Test**: As operator, open Ops → charts + thresholds + drift status +
retrain history render; controls present and operator-gated. Non-operator denied.

- [X] T050 [US4] EXTEND the existing `backend/app/api/ops.py` (created in T041) with the read endpoints `GET /ops/drift` (current + series + thresholds) and `GET /ops/retrains` (history with champion-vs-challenger) — do not recreate the file or re-register the router; add handlers behind the same `is_operator` dependency (contracts/http-api.md).
- [X] T051 [P] [US4] Create `frontend/src/api/opsApi.ts`: drift status/series, retrain history, models, retrain + promote clients.
- [X] T052 [P] [US4] Create `frontend/src/components/ConfidenceChart.tsx`: confidence + correction-rate series with threshold lines.
- [X] T053 [US4] Create `frontend/src/pages/Ops.tsx`: charts + drift status + retrain-history table + retrain/promote buttons; route in `frontend/src/App.tsx`; operator-only Ops link in `frontend/src/components/NavBar.tsx`.
- [X] T054 [P] [US4] Frontend test `frontend/src/pages/Ops.test.tsx`: renders charts/threshold lines, retrain-history rows with champion-vs-challenger numbers, and gates controls for non-operators.

**Checkpoint**: the loop is observable and operable; SC-008 verified in the UI.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T055 [P] Add structlog spans with request IDs across the drift, slack, and trainer paths (token/cost fields where an LLM call is made) (Art. V).
- [X] T056 [P] Add the Gate #7 step to `.github/workflows/ci.yml` (run `test_drift_gate.py` with `USE_FAKE_LLM=true`, stack-independent); ensure the new unit/integration tests run in the existing jobs.
- [X] T057 [P] Confirm `docker-compose.yml` trainer service consumes the `training` RQ queue under the `training` profile (wire the command if needed); document the run in quickstart.
- [X] T058 [P] Append Phase-5 rows to `docs/DECISIONS.md`: lean-serving rule interpretation (trainer = the one heavy non-request-path image), partial-unfreeze recipe (R1), drift signals/thresholds (R4), Gate #7 stack-independence reconciliation (R5), global cooldown (R6), strict-beat gate (R9). Every number backed.
- [ ] T059 Run `specs/007-lifecycle-ops/quickstart.md` Scenarios 1–7 against the live stack (incl. `--profile training`); fix until all acceptance checkboxes pass.
- [ ] T060 Run `ruff check .`, `mypy .`, `pytest -q` in `backend/`, `pytest modelserver/tests` + `trainer` import check, and `npm run typecheck`/`lint`/`test` in `frontend/`; fix until all are zero-error and green.
- [ ] T061 Refresh the knowledge graph: `graphify update .`.

---

## Dependencies & Execution Order

- **Setup (Phase 1)** → **Foundational (Phase 2)** must complete before any user story.
- **US1 (P1)** is the MVP and the source of human-confirmed labels; it depends only on
  Phase 2.
- **US2 (P2)** depends on Phase 2 (registry/runs) and on US1 producing confirmed labels
  for a *meaningful* retrain (the trigger/gate code is testable independently with fixtures).
- **US3 (P3)** depends on Phase 2 (drift table) and reuses US2's retrain trigger (it
  enqueues via the same path); testable independently with the committed fixture + fakes.
- **US4 (P4)** visualizes US2 + US3 data; its read endpoints depend on the
  registry/runs/drift repos (Phase 2) and share `api/ops.py` with US2 (sequential on that
  file).
- **Polish (Phase 7)** last.

## Parallel Opportunities

- **Phase 1**: T002, T003, T004, T005 in parallel (distinct files) after T001.
- **Phase 2**: T007–T016 are mostly `[P]` (distinct domain/repo files) after the T006
  migration.
- **US1**: tests T017/T018 in parallel; T025/T026/T028 frontend in parallel with backend
  T020–T024.
- **US2**: tests T029–T032 in parallel; T038 (model-server provider) parallel with backend
  service work; T040 parallel.
- **US3**: T042/T043/T044 in parallel; worker impls T045/T046 sequential where they share
  the trigger.
- **US4**: T051/T052/T054 in parallel with the T050 endpoint.

## Implementation Strategy

**MVP = Phase 1 + Phase 2 + US1.** That alone delivers a working review queue and a
human-confirmed corrections store (the foundation for everything else). Then add **US2**
(the headline gated-retrain loop, SC-001), **US3** (drift + Slack + Gate #7), and finally
**US4** (the ops dashboard). Each story is independently testable; ship incrementally.
