# Data Model: Evals, Demo & Release

Phase 7 introduces no new persistent entities. All entities below are in-process or
file-based; they do not require database migrations.

---

## EvalThreshold (file: eval_thresholds.yaml)

A named gate threshold entry. Each gate section in `eval_thresholds.yaml` contains:

| Field | Type | Description |
|-------|------|-------------|
| gate_name | string | e.g., `categorizer`, `forecaster`, `rag` |
| threshold_key | string | e.g., `macro_f1_min`, `beat_baseline`, `hit_at_5_min` |
| committed_value | float / bool / null | The pass threshold committed to source |
| last_measured | float / null | Annotation added by Phase 7 with actual value |
| note | string / null | Explanation (e.g., FakeEmbedder limitation for RAG) |

State transitions: thresholds are append-only; once set they are only ratcheted UP
(never down), per constitution Art. V.

---

## DemoUser (in Postgres: users + transactions tables)

Two synthetic users seeded by `scripts/seed_demo.py`:

| Field | Value |
|-------|-------|
| email | demo@raseed.app, demo2@raseed.app |
| hashed_password | argon2 hash of "Demo1234!" / "Demo5678!" |
| is_active | true |
| is_verified | true |

**DemoTransaction** (per demo user, ~180 rows covering 6 months):

| Field | Type | Description |
|-------|------|-------------|
| user_id | UUID | FK → demo user |
| occurred_at | timestamptz | random date in [-180, 0] days |
| amount | numeric(10,2) | realistic GBP amounts per category |
| description | text | UK merchant names matching Phase 2 taxonomy |
| type_code | varchar(8) | DEB / BP / DD / FPI / BGC / CPT |
| category | varchar(32) | one of the 18 Phase-2 taxonomy classes |
| label_source | varchar(16) | "human" (seeded as confirmed) |
| needs_review | bool | false (seeded data is pre-confirmed) |

Idempotency: `INSERT … ON CONFLICT (email) DO NOTHING` on users;
`INSERT … ON CONFLICT ON CONSTRAINT transactions_dedup_key DO NOTHING` on transactions.

---

## GoldenSet (committed YAML/Parquet files — read-only in Phase 7)

Pre-existing fixtures; Phase 7 does not modify them.

| File | Gate | Format |
|------|------|--------|
| `backend/tests/golden/tool_selection/cases.yaml` | Gate 3 | 15 cases: message + expected_route + expected_tool |
| `backend/tests/golden/rag/triples.yaml` | Gate 4 | passage-question-answer triples |
| `backend/tests/golden/forecasting/history.parquet` | Gate 2 | historical spend time series |
| `training/data/holdout.parquet` | Gate 1 | labeled transactions (never used in training) |

---

## ReleaseTag (git)

| Field | Value |
|-------|-------|
| name | `v0.1.0` |
| target | merge commit on main after all gates green |
| message | "Raseed v0.1.0 — all 8 CI gates green; see docs/EVALS.md" |
