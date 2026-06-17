# Implementation Plan: The ML Lifecycle & Ops

**Branch**: `007-lifecycle-ops` | **Date**: 2026-06-17 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/007-lifecycle-ops/spec.md`

## Summary

Close the ML loop. A user's low-confidence (`needs_review`) transactions surface in
a **review queue**; each human decision writes a **human-provenance correction**, the
only label kind allowed to train. A per-user setting can auto-relabel flagged rows
via Flash-Lite (provenance `llm`) but those land in a **quarantine** the owning user
must confirm before they become training data. Accumulated confirmations (or a
14-day cooldown, an operator's manual button, or a primary-signal drift alarm) trip a
**single global, idempotent retrain trigger** that enqueues one job on the RQ
`training` queue. The **trainer** (the one heavy, torch image, `training` compose
profile, never on a request path) runs a partial-unfreeze CPU retrain on confirmed
labels and ships a new ONNX + model card + SHA to MinIO. A **champion/challenger
gate** scores the challenger against the champion on the untouched Phase-2 frozen
holdout; results land in the `model_registry`. Promotion is **operator-only** (HIL,
`is_operator`): on promote, the registry swaps champion↔archived and the **model-server
reloads** the new artifact by SHA (refuse-on-mismatch). A **drift monitor** on the
light worker (daily + on-demand) tracks mean confidence + correction rate (primary →
alarm + Slack + retrain) and PSI + new-merchant rate (secondary → alarm + Slack only);
`scripts/simulate_drift.py` makes it demonstrable and drives **CI gate #7**. A **Slack
webhook** (URL from Vault) carries ops signals only — drift, retrain results,
aggregate anomaly rates — never user-level data, with timeout/retry/backoff and
non-blocking delivery. An **operator-only ops page** charts confidence/correction with
thresholds, drift status, and retrain history with champion-vs-challenger numbers, plus
the retrain and promote controls.

## Technical Context

**Language/Version**: Python 3.12 (backend, trainer, model-server, light worker);
TypeScript 5.4 / React 18.3 (frontend).

**Primary Dependencies**: Existing — FastAPI (async, layered), async SQLAlchemy,
Postgres, Redis (RQ), the Phase-1 LLM adapter (`infra/llm.py`, Flash-Lite mechanical /
Grok failover), structlog, tenacity (`with_retry`), the Phase-1 Vault adapter
(`infra/vault.py`), the model-server artifact seam (`get_current_artifact()`), and the
Phase-2 holdout gate logic (`training/gate_holdout.py`). Added — a MinIO client in
`infra/minio.py` (artifact bucket only); `torch` + `transformers` already declared in
the trainer image (`trainer/pyproject.toml`) for the partial-unfreeze retrain; `numpy`/
`scipy`-class math for PSI (numpy already present in the worker). Frontend — existing
React Router v6 + Tailwind + a charting approach consistent with the Phase-3b dashboard;
no new runtime libs assumed.

**Storage**: Postgres (Alembic `0005_lifecycle_ops`) — extend `model_registry`
(artifact_uri, holdout metrics JSONB, trigger origin, parent/challenger linkage,
promoted_by/promoted_at); new `retrain_runs` (trigger reason, status, challenger ref,
champion-vs-challenger metrics, idempotency key); new `drift_signals` (per-evaluation
metric snapshot + thresholds + fired flag); extend `corrections` (provenance + quarantine
state) and `users`/a settings row (review mode). MinIO — model artifacts by SHA
(`model-artifacts` bucket, the only writer is the trainer; the only readers are the gate
and the model-server). Redis — the RQ `training` queue and the global retrain
cooldown/idempotency key. Raw user files are never persisted (Art. II).

**Testing**: pytest (unit + integration) with committed fixtures so CI stays
stack-independent (Art. V): a frozen-holdout reuse from Phase 2 (Git LFS), a committed
skewed held-out-merchant batch for drift simulation, `FakeLLM` for relabel, and a
fakeable RQ queue for the enqueue assertions. Two acceptance-critical tests: **CI gate
#7** (`simulate_drift` → primary signal crosses → alarm fires → retrain enqueued) and a
**Slack-payload test** proving zero user-level data in every alert type. Frontend:
Vitest + React Testing Library.

**Target Platform**: Linux server (Docker Compose); the trainer runs only under the
`training` profile / `training` RQ queue. Modern desktop browsers for the SPA.

**Project Type**: Web application — FastAPI backend + React SPA + two off-request-path
images (light worker, trainer) + the lean model-server.

**Performance Goals**: Lifecycle actions are off the request path (worker/trainer), so
no user-facing latency budget applies to retrain/drift. Slack delivery is non-blocking
with respect to any request (Art. V). The drift monitor runs once daily + on demand; a
single retrain runs per cooldown window.

**Constraints**: In-stack retrains are **partial-unfreeze on CPU only — never full
fine-tunes** (initial foundation training stays in Colab). No torch/transformers in any
serving image — the trainer is the single deliberately heavy image, off the default
profile, never on a request path (Art. III). Only human-confirmed labels train (Art.
III). Promotion requires beats-champion AND operator approval (Art. III). Model-server
refuses to boot/reload on SHA mismatch (Art. III). Slack payloads carry ops signals
only — never user-level transaction data or identifiers (Art. II). Slack webhook URL
resolves from Vault (Art. V). Every tuned number recorded in `DECISIONS.md` (Art. V).

**Scale/Scope**: Single-instance demo scale — tens of corrections to trip the demo
threshold (10), hundreds at the production threshold (100). One trainer job per cooldown
window; one champion at a time. ~3 new backend API routers (review, ops, settings), 2
worker jobs (drift, slack), 1 trainer implementation, 1 model-server reload path + MinIO
provider, ~4 new tables/extensions, 1 ops page + 1 review queue UI.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Art. I — Layered, Async Architecture**: New code stays layered — `api/review.py`,
  `api/ops.py`, `api/settings.py` (HTTP only) → `services/review/*`, `services/lifecycle/*`
  (logic) → `repositories/*` (SQL) → `domain/*`. `infra/minio.py` is the MinIO adapter;
  the LLM relabel reuses `infra/llm.py`; Slack/drift run in the worker layer
  (`app/workers/*`), off the request path. Backend I/O is awaited; the operator promote
  path calls the model-server `/reload` via the async client. Errors map through
  `RaseedError`. The trainer (`trainer/train.py`) and workers are separate processes, not
  request handlers. **PASS**
- **Art. II — Isolation & Data Protection (NON-NEGOTIABLE)**: The review queue and the
  LLM-relabel quarantine are user-scoped under RLS (`app.user_id`); quarantined relabels
  are confirmed only by the owning user and are NEVER surfaced to operators
  (clarification 2026-06-17). The drift monitor and population-style stats run as the
  privileged cross-user job (not under a user session) and emit only aggregates. Slack
  payloads and the ops page carry only model/ops aggregates — no descriptions, amounts,
  merchants, or user IDs — enforced by a dedicated test (SC-004). MinIO holds model
  artifacts only. **PASS**
- **Art. III — ML Lifecycle Integrity**: This phase *is* Art. III. Provenance
  `rule|model|llm|human` already exists; only `human`-confirmed corrections enter a
  training batch (LLM relabels quarantined until confirmed). The frozen holdout is reused
  read-only by the gate. The trainer is the single heavy image (torch), `training`
  profile + `training` queue, never on a request path; serving images stay lean
  (onnxruntime + numpy). Artifacts ship a model card + pinned SHA; the model-server
  refuses to boot/reload on mismatch. A challenger is promoted ONLY if it beats the
  champion AND an operator approves. **PASS**
- **Art. IV — Bounded Agent & Grounded RAG**: Unchanged this phase. The Phase-4
  `reclassify_transaction` write tool already records a human correction; no new agent
  surface or RAG path is added. **PASS (not in scope)**
- **Art. V — Quality & Operations**: The Slack sender and the model-server reload call
  use timeout + tenacity backoff (4xx not retried); Slack delivery is non-blocking and
  logs failures rather than propagating. Drift evaluation is a scheduled + on-demand
  worker job; nothing transaction-derived is time-expired. structlog spans with request
  IDs cover the worker and trainer paths. **Gate #7** (drift-fire) lands in
  `eval_thresholds.yaml` with a real value and runs stack-independently on a committed
  fixture + fakeable queue (reconciled in research R5). Secrets (Slack webhook URL,
  MinIO creds) resolve from Vault; nothing hardcoded. Every threshold (trigger counts,
  cooldown, drift thresholds, gate margin) recorded in `DECISIONS.md`. **PASS**

**Stack compliance**: Postgres, Redis/RQ, MinIO (artifacts only), Vault, the trainer
`training` profile, the lean model-server, and the React SPA are all the mandated stack.
No new infrastructure. **PASS** — no Complexity Tracking entries required.

## Project Structure

### Documentation (this feature)

```text
specs/007-lifecycle-ops/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── http-api.md      # review queue, settings, ops (charts/history/promote/retrain) wire shapes
│   ├── slack-payloads.md # ops-only alert schemas (drift / retrain / anomaly-rate) — the no-user-data contract
│   └── trainer-job.md   # RQ training-job contract: input (idempotency key), artifact+card+SHA output, registry write
└── tasks.md             # Phase 2 output (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── api/
│   │   ├── review.py                   # NEW — GET review queue, POST confirm/correct, GET/POST quarantine confirm
│   │   ├── settings.py                 # NEW — GET/PUT user review-mode setting
│   │   └── ops.py                      # NEW — operator-only: charts, drift status, retrain history, retrain+promote
│   ├── services/
│   │   ├── review/                     # NEW package
│   │   │   ├── queue.py                # needs_review listing + correction confirmation (human provenance)
│   │   │   └── relabel.py              # Flash-Lite auto-relabel (provenance=llm) + quarantine; reuses infra/llm.py
│   │   └── lifecycle/                  # NEW package
│   │       ├── trigger.py              # global idempotent retrain trigger (count/cooldown/manual/drift) + Redis lock
│   │       ├── gate.py                 # champion/challenger on frozen holdout (reuses training/gate_holdout logic)
│   │       └── promote.py              # operator promotion: registry swap + model-server /reload call
│   ├── repositories/
│   │   ├── corrections_repo.py         # NEW — corrections store + confirmed-since-last-retrain count
│   │   ├── model_registry_repo.py      # NEW — registry CRUD + champion/challenger queries
│   │   ├── retrain_runs_repo.py        # NEW — retrain run history
│   │   └── drift_repo.py               # NEW — drift signal snapshots + series for charts
│   ├── workers/
│   │   ├── drift.py                    # IMPLEMENT — primary+secondary signals, daily+on-demand, fire→alert→enqueue
│   │   ├── slack_webhook.py            # IMPLEMENT — ops-only payloads, Vault URL, timeout/retry/backoff, non-blocking
│   │   └── worker.py                   # EXTEND — register `training` queue + scheduler tick for daily drift
│   ├── infra/
│   │   ├── minio.py                    # IMPLEMENT — artifact upload/download by SHA (artifacts bucket only)
│   │   ├── queue.py                    # EXTEND — `training` queue + enqueue_retrain(idempotency_key)
│   │   ├── vault.py                    # EXTEND — add slack_webhook_url to resolved secrets
│   │   └── modelserver_client.py       # EXTEND — reload() call to model-server /reload
│   ├── domain/
│   │   ├── model_registry.py           # EXTEND — artifact_uri, metrics JSONB, trigger origin, linkage, promoted_by/at
│   │   ├── correction.py               # EXTEND — provenance + quarantine state
│   │   ├── retrain_run.py              # NEW — RetrainRun (trigger reason, status, metrics, idempotency key)
│   │   ├── drift_signal.py             # NEW — DriftSignal snapshot
│   │   └── user_settings.py            # NEW — per-user review-mode setting (or column on users)
│   ├── schemas/
│   │   ├── review.py                   # NEW — review item, correction, quarantine confirm
│   │   └── ops.py                      # NEW — chart series, drift status, retrain history, promote/retrain requests
│   └── alembic/versions/
│       └── 0005_lifecycle_ops.py       # NEW — registry/correction extends + retrain_runs + drift_signals + review mode
├── scripts/
│   └── simulate_drift.py               # NEW — inject committed skewed held-out-merchant batch (isolated), invoke monitor
└── tests/
    ├── fixtures/
    │   └── drift_skewed_batch.parquet  # NEW (committed) — held-out-merchant skewed batch for the drift gate
    ├── unit/
    │   ├── test_review_queue.py        # human correction → provenance=human, leaves needs_review
    │   ├── test_relabel_quarantine.py  # llm relabel quarantined; only owning-user confirm upgrades to human
    │   ├── test_retrain_trigger.py     # count/cooldown/manual/drift; global idempotency (one job/window); manual override
    │   ├── test_gate.py                # challenger beats champion (strict) / tie = no promote
    │   ├── test_drift_signals.py       # primary→enqueue+alert; secondary→alert only; PSI/new-merchant math
    │   └── test_slack_payload.py       # SC-004 — zero user-level data in every alert type
    ├── integration/
    │   ├── test_promote_reload.py      # operator promote → registry swap + model-server reload (mismatch aborts)
    │   └── test_operator_access.py     # non-operator denied ops page + retrain/promote (SC-008)
    └── test_drift_gate.py              # CI Gate #7 — simulate_drift → primary crosses → fire + enqueue (fixture + fake queue)

trainer/
└── train.py                            # IMPLEMENT — partial-unfreeze CPU retrain on human-confirmed labels;
                                        #   export ONNX + model card + SHA to MinIO; write challenger registry row

modelserver/
├── categorizer.py                      # EXTEND — get_current_artifact() gains a MinIO-by-SHA provider
└── app.py                              # EXTEND — POST /reload: re-resolve by SHA, re-verify, atomic swap (refuse on mismatch)

frontend/
└── src/
    ├── pages/
    │   ├── Review.tsx                  # NEW — review queue: confirm/correct, quarantine confirm, review-mode toggle
    │   └── Ops.tsx                     # NEW — operator-only: charts+thresholds, drift status, retrain history, buttons
    ├── components/
    │   ├── ReviewRow.tsx               # NEW — one flagged transaction with category control
    │   └── ConfidenceChart.tsx         # NEW — confidence/correction series with threshold lines
    ├── api/
    │   ├── reviewApi.ts                # NEW — review queue + settings client
    │   └── opsApi.ts                   # NEW — ops charts/history/retrain/promote client
    └── components/NavBar.tsx           # EXTEND — Review link (all users); Ops link (operators only)
```

**Structure Decision**: Web application, extended along the existing layered backend.
The phase implements three previously-stubbed worker/infra files (`workers/drift.py`,
`workers/slack_webhook.py`, `infra/minio.py`) and the `trainer/train.py` stub, adds two
service packages (`services/review/`, `services/lifecycle/`), thin operator-gated
routers, four new domain models/extensions, one Alembic migration, and a model-server
`/reload` path behind the existing artifact seam. The frontend adds a user-facing Review
page and an operator-only Ops page. CI gate #7 and the Slack-payload test run
stack-independently on committed fixtures (Art. V); the heavy trainer container itself is
exercised only in the demo/quickstart, never as a merge-blocking CI dependency.

## Complexity Tracking

> No constitution violations. No entries required.
