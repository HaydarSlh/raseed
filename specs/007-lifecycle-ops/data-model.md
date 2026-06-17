# Phase 1 Data Model: The ML Lifecycle & Ops

Migration: `backend/alembic/versions/0005_lifecycle_ops.py`. All user-data tables keep
`user_id` + RLS; the lifecycle/registry/drift tables are **global ops tables** (no
`user_id`), written by the privileged worker/trainer/operator paths and read aggregate-
only (Art. II). Reuses existing enums (`Provenance`, `ModelStatus`).

---

## Extended: `corrections` (existing — `domain/correction.py`)

Add quarantine/provenance semantics so LLM relabels are trackable and excluded from
training until confirmed.

| Field | Type | Notes |
|-------|------|-------|
| id | UUID PK | existing |
| user_id | UUID FK→users | existing, RLS-scoped |
| transaction_id | UUID FK→transactions (SET NULL) | existing |
| old_category | str? | existing |
| new_category | str | existing |
| confirmed_by_human | bool | existing — **only `true` rows are training-eligible** |
| **provenance** | enum(`llm`/`human`) | NEW — how this correction's new_category was set |
| **quarantined** | bool | NEW — `true` for an unconfirmed LLM relabel; `false` once human-confirmed |
| created_at | datetime | existing |
| **confirmed_at** | datetime? | NEW — set when a human confirms |

**Rules**: an LLM relabel inserts `provenance=llm, quarantined=true, confirmed_by_human=false`.
Owning-user confirmation sets `provenance=human, quarantined=false, confirmed_by_human=true,
confirmed_at=now()`. Training queries select `confirmed_by_human=true` only (FR-007).

**State transitions**: `quarantined(llm) → confirmed(human)` (owning user only); a manual
human correction is born `confirmed(human)` directly.

---

## Extended: `model_registry` (existing — `domain/model_registry.py`)

Add the artifact pointer, holdout metrics, trigger origin, and promotion provenance.

| Field | Type | Notes |
|-------|------|-------|
| id, name, version, sha256, status, model_card, created_at | — | existing |
| **artifact_uri** | str | NEW — MinIO key `categorizer/<sha256>/…` (R3) |
| **metrics** | JSONB | NEW — holdout metrics (macro_f1, per_class_f1, latency_ms) |
| **retrain_run_id** | UUID FK→retrain_runs? | NEW — the run that produced this artifact (null for the Phase-2 foundation champion) |
| **promoted_by** | UUID FK→users? | NEW — operator who promoted (null while challenger/archived) |
| **promoted_at** | datetime? | NEW |

**Status lifecycle** (`ModelStatus`): `challenger → champion` (on operator promote) and
the prior `champion → archived` in the same transaction; a challenger that loses the gate
stays `challenger` (kept for history) and is never promoted. **Invariant: at most one
`champion` row at any time.**

`version` — semver; an in-stack retrain bumps the champion's MINOR (foundation training
owns MAJOR) (U3). The `model_card` JSONB additionally carries the **drift reference**
(training category histogram + normalized-merchant set) the drift monitor reads as its
PSI/new-merchant baseline (R4/U1).

---

## New: `retrain_runs` (`domain/retrain_run.py`) — global ops table

| Field | Type | Notes |
|-------|------|-------|
| id | UUID PK | |
| trigger_reason | enum(`correction_count`/`time_cooldown`/`manual`/`drift`) | which source fired |
| idempotency_key | str UNIQUE | one job per key (R6); duplicate enqueue rejected |
| status | enum(`enqueued`/`running`/`completed`/`failed`/`skipped`) | `skipped` = too few eligible labels (FR-012) |
| skipped_reason | str? | populated when status=`skipped` |
| challenger_id | UUID FK→model_registry? | the produced challenger (null if skipped/failed) |
| champion_macro_f1 | float? | gate comparison (R9) |
| challenger_macro_f1 | float? | gate comparison |
| gate_verdict | enum(`beats`/`does_not_beat`)? | strict-beat result (tie = does_not_beat) |
| labels_used | int? | count of human-confirmed corrections trained on |
| created_at | datetime | |
| completed_at | datetime? | |

**Relationships**: one run → at most one challenger registry row; the registry row links
back via `retrain_run_id`.

---

## New: `drift_signals` (`domain/drift_signal.py`) — global ops table

One row per monitor evaluation (daily or on-demand), capturing every signal snapshot so
the ops charts can plot history with thresholds.

| Field | Type | Notes |
|-------|------|-------|
| id | UUID PK | |
| evaluated_at | datetime | |
| mean_confidence | float | primary signal value |
| correction_rate | float | primary signal value |
| psi | float | secondary signal value |
| new_merchant_rate | float | secondary signal value |
| thresholds | JSONB | the thresholds in effect at evaluation (for chart lines) |
| fired | bool | any signal crossed |
| fired_signals | JSONB | list of crossed signal names (primary vs secondary) |
| triggered_retrain | bool | true only when a PRIMARY signal crossed (R4) |
| source | enum(`scheduled`/`on_demand`/`simulation`) | provenance of the evaluation |

**Rule**: `triggered_retrain=true` ⇒ a `retrain_runs` row with `trigger_reason=drift`
exists (subject to the FR-009 cooldown).

---

## New: per-user review-mode setting

Smallest correct form: a `review_mode` column on a new `user_settings` table keyed by
`user_id` (1:1), or a column on `users`. Plan picks **`user_settings`** to avoid touching
the fastapi-users table.

| Field | Type | Notes |
|-------|------|-------|
| user_id | UUID PK FK→users | RLS-scoped |
| review_mode | enum(`manual`/`auto_relabel`) | default `manual` (FR-004) |
| updated_at | datetime | |

---

## Reused, unchanged

- **`transactions`** — `provenance`, `confidence`, `needs_review`, `merchant`,
  `normalized_description`, `category` already present (Phase 3). Drift reads
  `confidence`/`provenance`/`merchant`; the review queue reads `needs_review`.
- **`users.is_operator`** — already present (Phase 1); gates ops/promote/retrain (R10).
- **Frozen holdout** — committed Git LFS artifact reused read-only by the gate (R9).
- **MinIO `model-artifacts` bucket** — artifact storage (R3); no schema.
- **`model_card.json`** (per artifact in MinIO) — carries holdout metrics AND the drift
  reference: training category histogram + normalized-merchant set. The drift monitor
  reads the current champion's card as the PSI/new-merchant baseline (R4/U1).

## Validation rules (from requirements)

- A training batch MUST select only `corrections.confirmed_by_human=true` (FR-007, SC-002).
- At most one `model_registry.status='champion'` (promotion invariant, FR-017).
- `retrain_runs.idempotency_key` UNIQUE ⇒ one job per cooldown window (FR-009, SC-006).
- Promote requires `gate_verdict='beats'` AND operator (FR-015/016, SC-005).
- `drift_signals.triggered_retrain` only on primary crossings (FR-019).
