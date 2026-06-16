# Internal Contracts — Ingestion Service, Jobs, CI Gate

## `ingest_transactions(user_id, rows) -> IngestResult`  (services/ingestion.py)

The single shared ingestion function. Same path for upload, manual form, and (future) agent
tool.

- **Input**: `user_id` (from JWT context), `rows: list[ParsedRow]` (already parsed +
  PAN/IBAN-scrubbed; `txn_date`, `amount`, `description`).
- **Steps** (in order):
  1. Normalize description; compute dedup key `(user_id, txn_date, amount, normalized_description)`;
     skip rows matching an existing key.
  2. **Rules layer** (`services/rules.py`): known-merchant lookup → `category`, `provenance=rule`,
     `confidence=1.0`. Unmatched rows fall through.
  3. **Model-server call** for unmatched rows → `category`, `confidence` (awaited; batched where
     possible).
  4. **Confidence gate**: `confidence ≥ category_threshold` → `provenance=model`,
     `needs_review=false`; else `needs_review=true`. `always_review` categories → always
     `needs_review=true`.
  5. Persist enriched rows (user-scoped).
- **Output**: `IngestResult { ingested, needs_review, duplicates_skipped }`.
- **Invariants**: never persists raw bytes; never accepts `user_id` from a request body; fails
  without partial unscrubbed/uncategorized persistence if the model-server is unavailable.

## `recompute_worker(user_id)`  (workers/recompute_worker.py, RQ)

- Triggered by every transaction write (upload/form/future reclassify).
- Recomputes and **replaces** the user's `forecasts`, `anomalies`, `subscriptions` from current
  history; sets `transactions.is_anomaly`.
- Idempotent: re-running for the same history yields the same derived rows.

## `population_stats_job()`  (workers/population_stats_job.py — PRIVILEGED, periodic)

- Runs with no user RLS context; aggregates across all users into `population_stats`.
- Emits only anonymized rows (`category`, `day_of_week`, `mean`, `stddev`) and only when the
  contributing-user count ≥ k-anonymity threshold. No `user_id`, no identifiers.
- Never invoked from a request path; user-scoped sessions may only **read** `population_stats`.

## Forecaster contract (services/forecasting.py)

- `forecast(user_history) -> Forecast` decomposes known recurring (deterministic) vs variable
  discretionary (Prophet), returns 30 daily points with `lower/upper` bounds and `is_cold_start`.
- Cold start (`< 30 days` history): blend day-of-week averages with `population_stats` prior.
- **Baseline**: `day_of_week_baseline(user_history)` — the value the forecaster must beat (MAE).

## CI Gate #2 — forecaster MAE (eval_thresholds.yaml `forecaster`)

- Runs `python` over `backend/tests/golden/forecasting/` (committed fixture, Git LFS).
- **PASS iff** `forecaster_MAE ≤ baseline_MAE` (and ≤ committed `mae_max` if set).
- Never touches the live DB or compose stack (constitution Art. V). Wired as a CI job like the
  Phase-2 categorizer gate.
