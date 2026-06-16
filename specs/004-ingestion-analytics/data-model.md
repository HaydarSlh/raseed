# Data Model — Ingestion & Analytics

All user tables carry `user_id` and are protected by Postgres RLS keyed on the per-request
`app.user_id` session variable (constitution Art. II). `population_stats` is the sole
exception: it has **no `user_id`**, holds only anonymized aggregates, and is written only by
the privileged job. Derived tables (`forecasts`, `anomalies`, `subscriptions`) are
invalidated and recomputed on any transaction write (Art. V) — never read-time computed.

## Enums

- **Provenance**: `rule | model | human` (LLM provenance reserved for later phases).
- **AnomalyType**: `statistical_outlier | duplicate_charge`.
- **Cadence**: `weekly | biweekly | monthly | quarterly | annual | irregular`.

## `transactions` (enriched) — user-scoped

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID PK | |
| `user_id` | UUID | from JWT only; RLS key |
| `txn_date` | date | |
| `amount` | numeric(12,2) | signed: negative = debit/spend, positive = credit/income |
| `description` | text | PAN/IBAN already scrubbed by the parser |
| `normalized_description` | text | lowercased/trimmed; part of the dedup key |
| `category` | text | member of the locked taxonomy (Phase 2) |
| `confidence` | numeric | 1.0 for rule provenance |
| `provenance` | Provenance | |
| `needs_review` | bool | true when confidence < category threshold or `always_review` |
| `is_anomaly` | bool | denormalized flag set by recompute (detail in `anomalies`) |
| `created_at` | timestamptz | |

- **Uniqueness / dedup**: unique on `(user_id, txn_date, amount, normalized_description)`;
  conflicting inserts are skipped (R8).
- **Validation**: `amount` non-zero; `category` in taxonomy; `confidence ∈ [0,1]`.
- **State**: `needs_review = true` rows may transition to `false` + `provenance = human` when a
  user confirms (the confirmation UI is Phase 5; the column + transition exist now).

## `forecasts` — user-scoped, derived

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID PK | |
| `user_id` | UUID | RLS key |
| `horizon_date` | date | one row per day across the 30-day horizon |
| `projected_balance` | numeric(12,2) | point estimate |
| `lower_bound` | numeric(12,2) | likely-range low |
| `upper_bound` | numeric(12,2) | likely-range high |
| `is_cold_start` | bool | true when produced by the cold-start fallback |
| `computed_at` | timestamptz | recompute timestamp |

- One forecast set per user; replaced wholesale on recompute.

## `anomalies` — user-scoped, derived

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID PK | |
| `user_id` | UUID | RLS key |
| `transaction_id` | UUID FK → transactions | |
| `anomaly_type` | AnomalyType | |
| `score` | numeric | robust z / IQR distance (null for duplicates) |
| `reason` | text | human-readable explanation |
| `computed_at` | timestamptz | |

## `subscriptions` (recurring series) — user-scoped, derived

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID PK | |
| `user_id` | UUID | RLS key |
| `merchant` | text | normalized merchant key |
| `cadence` | Cadence | |
| `typical_amount` | numeric(12,2) | |
| `next_charge_date` | date | predicted |
| `price_increase` | bool | true when the recent amount stepped up |
| `last_amount` | numeric(12,2) | most recent observed |
| `computed_at` | timestamptz | |

## `population_stats` — GLOBAL, anonymized (no user_id)

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID PK | |
| `category` | text | taxonomy category |
| `day_of_week` | smallint | 0–6 |
| `mean_amount` | numeric(12,2) | anonymized aggregate |
| `stddev_amount` | numeric(12,2) | |
| `user_count` | int | k-anonymity guard (only emitted when ≥ threshold users) |
| `computed_at` | timestamptz | |

- **Privacy**: written only by `population_stats_job.py` (privileged, no RLS user context);
  contains no `user_id` or identifying fields; rows below a minimum contributing-user count are
  not emitted (k-anonymity). No request-time session writes here.

## Relationships

- `anomalies.transaction_id` → `transactions.id` (same user; FK + RLS).
- `subscriptions` and `forecasts` reference a user's transaction history but store only derived
  results.
- `population_stats` is independent of any user; consumed read-only by the cold-start path.

## Transient (never persisted)

- **Ingestion batch**: the parsed in-memory rows from an upload. Exists only during
  `ingest_transactions`; raw file bytes are discarded immediately after parsing (Art. II).
