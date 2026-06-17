# Phase 0 Research: The ML Lifecycle & Ops

All decisions below resolve the Technical Context unknowns and the brief's "Notes for
/plan". Each is grounded in the existing codebase (Phase 0–4 scaffolding) and the
constitution. Tuned numbers are flagged for `DECISIONS.md`.

---

## R1 — Partial-unfreeze CPU retrain recipe

**Decision**: The trainer runs a **partial-unfreeze** fine-tune: load the current
champion's base weights, freeze the transformer encoder except the top N layers (start
N=2) + the classification head, train a small number of epochs (start 3) on the
accumulated human-confirmed corrections joined to their transaction text, then temperature-
calibrate on the val split and export ONNX — mirroring `training/train_champion_local.py`
but seeded from the champion rather than from scratch. CPU-only (no CUDA in the image).

**Rationale**: A partial unfreeze adapts the model to new labels at a CPU-affordable
cost and avoids catastrophic forgetting of the Colab foundation training. It honors the
brief's hard rule: **in-stack retrains are never full fine-tunes**; the foundation model
stays a Colab/GPU artifact. The recipe already exists locally (`train_champion_local.py`)
and produces ONNX via `training/export_onnx.py`.

**Alternatives considered**: (a) Full fine-tune in-stack — rejected, violates the brief
and the lean-CPU budget. (b) Classical TF-IDF+LR re-fit only — rejected, the champion is
the neural artifact path; but if the champion is the classical baseline, the trainer
re-fits the pipeline instead (the trainer branches on champion model type, which
`categorizer.py` already detects). (c) GPU in-stack — rejected, no CUDA in any image.

**For DECISIONS.md**: unfreeze depth (top-2 layers + head), epoch count (3), CPU time
budget — finalized when the trainer runs on real accumulated corrections.

---

## R2 — Model-server reload mechanism

**Decision**: Add `POST /reload` to the model-server. It re-invokes the
`get_current_artifact()` seam (now MinIO-by-SHA, R3), recomputes and re-verifies the
SHA-256 (same refuse path as boot), constructs a fresh `Categorizer`, and **atomically
swaps `app.state.categorizer`** on success. On any failure (missing artifact, SHA
mismatch, load error) it returns a structured error and **keeps the existing
categorizer** — never serves a half-loaded or mismatched model. The backend's
`promote.py` calls it through the async `modelserver_client` after the registry swap.

**Rationale**: Hot reload avoids container downtime in the demo and keeps the swap under
the same hash-verification invariant the boot path already enforces (Art. III). The
artifact seam was explicitly designed for this ("Phase 5 swaps in a MinIO-by-SHA
provider … without touching boot or hash-verification logic").

**Alternatives considered**: (a) Restart the model-server container on promote —
rejected, introduces downtime and a compose-orchestration dependency on the request
path. (b) Model-server polls the registry — rejected, adds a polling loop and DB
coupling to the lean serving image; an explicit push from the operator action is simpler
and auditable.

---

## R3 — MinIO-by-SHA artifact provider

**Decision**: Implement `infra/minio.py` (backend) for **upload** (trainer side, via the
trainer's own MinIO access) and the model-server's `get_current_artifact()` MinIO
provider for **download-by-SHA**. Bucket layout in the existing `model-artifacts`
bucket: `categorizer/<sha256>/categorizer.onnx` and `…/tokenizer.json`, plus a
`model_card.json`. The model-server resolves *which* SHA is current from the
`model_registry` champion row's `sha256` (passed in the `/reload` call payload or read
via a tiny read-only lookup), downloads to a local cache dir, then runs the existing
SHA verification before loading.

The model-server does NOT independently resolve "current": the backend promote path
passes the just-promoted `sha256` in the `/reload` call, and the server only
downloads-by-that-SHA and verifies it. Single source of truth = the promoting backend
(resolves C2).

**Rationale**: Content-addressed paths make the artifact immutable and the SHA the
single source of identity — exactly what refuse-to-boot/reload checks against. Reuses the
existing `minio_artifacts_bucket` setting and keeps MinIO "artifacts only" (Art. II).

**Alternatives considered**: (a) `latest/` mutable pointer object — rejected, mutable
paths break content-addressing and complicate rollback. (b) Ship artifacts on a shared
volume — rejected, MinIO is the mandated artifact store and survives container
rebuilds.

---

## R4 — Drift signals: definitions, windows, thresholds

**Decision**: Compute on the production model's recent predictions (privileged
cross-user job, aggregates only):
- **Primary — mean confidence**: rolling mean of `transactions.confidence` over the last
  evaluation window; fires when it drops below `mean_confidence_min`.
- **Primary — correction rate**: human corrections ÷ model-labeled transactions over the
  window; fires above `correction_rate_max`.
- **Secondary — PSI** on category distribution: Population Stability Index of recent
  predicted-category distribution vs the training/reference distribution; fires above
  `psi_max` (alarm only).
- **Secondary — new-merchant rate**: share of transactions whose normalized merchant was
  unseen in the training reference; fires above `new_merchant_rate_max` (alarm only).

Only **primary** crossings enqueue a retrain (clarification 2026-06-17); secondary
crossings alarm + Slack only. Cadence: once daily on the light worker + on-demand
(R6/R8). Window: trailing 7 days (demo: since-last-evaluation over the simulated batch).

**Rationale**: Confidence + correction rate are the direct "model is wrong more often"
signals and are cheap to compute from existing columns (`confidence`, `provenance`,
`corrections`). PSI and new-merchant rate are standard distribution-shift diagnostics but
noisier, so they inform rather than auto-trigger. The simulated held-out-merchant batch
drives confidence down (unfamiliar merchants → low confidence), so it trips a *primary*
signal — making CI gate #7's "fires AND enqueues" coherent with "primary-only retrain".

**Reference distribution**: at export time the trainer writes, into the champion's
`model_card.json`, (a) the training category histogram and (b) the set (hash-set) of
normalized training merchants. The drift monitor loads these from the current champion's
card (via MinIO) as the PSI baseline and the new-merchant reference. No new table; the
reference travels with the artifact and rotates on promotion (resolves U1).

**For DECISIONS.md**: `mean_confidence_min`, `correction_rate_max`, `psi_max`,
`new_merchant_rate_max`, window length — seeded from the holdout's confidence
distribution and tuned with `simulate_drift.py`.

---

## R5 — CI gate #7 vs the stack-independence rule

**Decision**: The merge-blocking **gate #7** runs **stack-independent**: it loads the
committed skewed-batch fixture, runs the drift detection function directly, asserts a
primary signal crosses threshold, asserts the Slack sender is invoked (with a fake
transport), and asserts `enqueue_retrain` is called (with a fake/in-memory RQ queue) —
**without booting the trainer container or Redis**. The "training profile enabled"
intent from the brief is satisfied by exercising the *training-queue enqueue path* (the
job is enqueued to the `training` queue name), not by running the heavy image in CI.

**Rationale**: Reconciles the brief ("CI runs with the training profile … so the path is
genuinely tested") with the non-negotiable Art. V rule ("CI NEVER depends on the running
stack"). The genuinely tested path is *detection → alert → enqueue*; actually executing a
torch retrain in CI would be slow, flaky, and stack-dependent. The full
container-executed loop is proven in the **quickstart** demo instead.

**Alternatives considered**: (a) Run `docker compose --profile training` in CI —
rejected, violates Art. V and is minutes-slow. (b) Skip the enqueue assertion — rejected,
the enqueue is the whole point of the gate.

**For DECISIONS.md**: gate #7 value `must_fire_on_simulated_drift: true`.

---

## R6 — Retrain trigger: global cooldown & idempotency

**Decision**: One **global** trigger evaluator (`services/lifecycle/trigger.py`). It
fires when ANY source qualifies — confirmed-correction count since last retrain ≥
threshold (prod 100 / demo 10), OR ≥14 days since last retrain, OR a primary drift
alarm, OR the operator's manual button. A **single Redis-held cooldown/idempotency key**
(`retrain:cooldown`, TTL = cooldown window) gates all sources: if the key exists, no new
job is enqueued — **except** the operator's manual button, which sets a force flag that
bypasses (and resets) the key. On enqueue, a `retrain_runs` row is created with a unique
idempotency key; the worker refuses a duplicate key.

**Rationale**: A single shared lock is the simplest correct defense against retrain
storms when multiple sources coincide (FR-009, SC-006). The manual override preserves
operator control. Redis already backs RQ, so the lock needs no new infra.

**Alternatives considered**: (a) Per-source cooldowns — rejected by clarification
(2026-06-17), permits storms. (b) DB advisory lock only — viable but Redis TTL gives the
cooldown window for free and matches the existing queue infra.

**For DECISIONS.md**: cooldown window length (start = 14 days, aligned to the time
trigger), demo threshold (10), prod threshold (100).

---

## R7 — Slack webhook: payload contract, retry, non-blocking

**Decision**: Implement `workers/slack_webhook.py` as a function that posts a JSON
payload to an **incoming-webhook URL resolved from Vault** (add `slack_webhook_url` to
`infra/vault.py` required secrets; local `.env` fallback documented). Three payload
shapes (contracts/slack-payloads.md), each **aggregates-only**: drift alarm (signal name,
metric value, threshold, fired flag), retrain result (run id, trigger reason, gate
verdict, champion vs challenger macro-F1), anomaly-rate summary (count/rate, period).
Delivery uses `with_retry` (timeout + exponential backoff, 4xx not retried) and runs as
a worker job so it **never blocks a user-facing request**; failures are logged, not
raised.

**Rationale**: Directly implements FR-021/022/023 and Art. II/V. Reuses the existing
`with_retry` and Vault patterns. A frozen allowlist of payload fields (no free-form
transaction text) is what the SC-004 test asserts against.

**Alternatives considered**: (a) Send inline from the request path — rejected, blocks the
user and risks coupling a Slack outage to a user request. (b) Rich Block Kit messages
with per-transaction detail — rejected, would leak user-level data.

---

## R8 — Review queue & LLM relabel

**Decision**: `services/review/queue.py` lists the signed-in user's `needs_review`
transactions (RLS-scoped) and confirms corrections (writes `corrections` row,
`confirmed_by_human=true`, provenance `human`, clears `needs_review`) — reusing the
Phase-4 correction-writing path. `services/review/relabel.py` handles the auto mode: for a
user whose setting is "automatic", flagged rows are relabeled via the **Flash-Lite**
adapter tier (`infra/llm.py`, mechanical), written with provenance `llm` and a
`quarantined=true` state, and surfaced in the user's queue as "awaiting confirmation".
Only the owning user's confirmation upgrades provenance to `human` (clarification
2026-06-17). Relabel runs as a worker job (batched), not on the request path.

**Rationale**: Matches FR-001–007 and the clarified owning-user quarantine rule. Keeps
the single correction-writing path (Art. III) and uses the mechanical LLM tier for a
cheap, bounded relabel. Worker-side batching keeps the request path responsive.

**Alternatives considered**: (a) Relabel synchronously on queue load — rejected, an LLM
call per flagged row would block the UI. (b) Operator-reviewed quarantine — rejected by
clarification (data-isolation concern).

---

## R9 — Champion/challenger gate reuse

**Decision**: `services/lifecycle/gate.py` reuses the **exact Phase-2 holdout gate
logic** (`training/gate_holdout.py`: `C − B ≥ beat_baseline_margin` AND `C ≥
macro_f1_min` AND per-class floor AND latency bound) on the **untouched frozen holdout**
(committed via Git LFS). Here B = the current champion's holdout macro-F1 and C = the
challenger's; promotion additionally requires the challenger to **strictly beat** the
champion (a tie does not beat — FR-015 / edge case) AND operator approval. Both models'
metrics and the verdict are written to `retrain_runs` + `model_registry`.

**Rationale**: Reusing the established gate avoids a second, divergent definition of
"good" (Art. III, Art. V "don't invent a second threshold"). The frozen holdout is touched
only by this gate, preserving its integrity.

**Where it runs**: in the trainer process (it already loads both models + the holdout
and carries sklearn/pandas). The backend `services/lifecycle/gate.py` only reads the
persisted verdict — no scoring deps (sklearn/holdout load) enter the lean backend image
(Art. III lean-serving spirit; resolves C1).

**Alternatives considered**: (a) New validation split per retrain — rejected, breaks the
frozen-holdout guarantee. (b) Promote on ≥ (tie allowed) — rejected by the spec's tie
rule.

---

## R10 — Operator gating & ops data

**Decision**: Operator-only endpoints (`api/ops.py`, the retrain/promote actions) depend
on a FastAPI dependency that asserts `current_user.is_operator` (the column already
exists), returning 403 otherwise. The ops page reads aggregate series from
`drift_repo`/`retrain_runs_repo`/`model_registry_repo` — never per-user transaction rows.
Operator assignment stays administrative (seed/DB), out of scope for a UI.

**Rationale**: `is_operator` already exists (Phase-1 user model); a thin dependency is the
minimal correct gate (FR-016, SC-008). Ops data is aggregate-only, consistent with Art.
II.

**Alternatives considered**: (a) Role table / RBAC — rejected as over-engineered for one
boolean this phase. (b) Surface per-user review data on ops — rejected (isolation).
