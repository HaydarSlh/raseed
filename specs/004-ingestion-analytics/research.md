# Phase 1 Research — Ingestion & Analytics

Decisions resolving the Technical Context, grounded in `docs/PLAN.md` DESIGN B/D and the
constitution. Format: Decision / Rationale / Alternatives.

## R1 — One ingestion function, multiple entry points

- **Decision**: A single `services/ingestion.py` function `ingest_transactions(user_id, rows)`
  performs parse-already-done → rules → model-server → confidence gate → dedup → store. The
  upload router (file → in-memory parse → rows) and the manual-form router (one row) both call
  it; the agent `add_transaction` tool (Phase 4) will too.
- **Rationale**: Brief "Notes for /plan" + DESIGN B: one path means one place for provenance,
  scrubbing, and the gate — no divergence between entry points.
- **Alternatives**: Separate upload vs form pipelines (rejected — duplicates the gate and
  scrubbing, invites drift).

## R2 — In-memory parse + PAN/IBAN scrub

- **Decision**: The upload router streams the file into the parser (`services/parsing.py`),
  which yields rows and scrubs PAN (card) and IBAN/account numbers via regex before returning;
  the file bytes are never written to disk, MinIO, or DB. v1 parses delimited CSV-class exports.
- **Rationale**: Constitution Art. II (raw files never persisted; PAN/IBAN scrubbed in the
  parser). Acceptance criterion: a test proves no raw bytes persist.
- **Alternatives**: Persist-then-parse (rejected — violates Art. II); arbitrary-PDF parsing
  (deferred per clarification).

## R3 — Confidence gate reuses the Phase-2 per-category thresholds

- **Decision**: After the model-server returns `category` + `confidence`, gate against the
  categorizer's committed per-category operating thresholds (`eval_thresholds.yaml`
  `operating_thresholds`): at/above → `provenance=model`; below or `always_review` →
  `needs_review`. Rule-matched rows skip the model with `provenance=rule`, confidence 1.0.
- **Rationale**: Reuses the calibrated, precision-targeted thresholds already validated in
  Phase 2 rather than inventing a second threshold. Provenance per constitution Art. III.
- **Alternatives**: A single global threshold (rejected — discards per-class calibration).

## R4 — Forecaster: decomposition + Prophet + day-of-week baseline + likely range

- **Decision**: Decompose history into (a) known recurring income/bills projected
  deterministically from the recurring detector, and (b) variable discretionary spend, which
  is the only series forecast. `balance = current + known_income − known_recurring −
  forecast_discretionary`. Use Prophet per user for the discretionary series; its native
  uncertainty interval becomes the dashboard likely range. The gate baseline is a day-of-week
  average; the forecaster must beat it on MAE.
- **Rationale**: DESIGN D verbatim. Deterministic projection of known items is more accurate
  and explainable than forecasting the whole balance; Prophet gives intervals for free.
- **Alternatives**: Forecast total balance directly (rejected — conflates deterministic and
  stochastic components, worse MAE); ARIMA/LightGBM (LightGBM is named future work).
- **Placement**: Prophet runs in the **light worker / backend off-request path**, NEVER in the
  lean model-server image (constitution Art. III — no torch/transformers/heavy deps in serving).

## R5 — Cold-start fallback + anonymized population prior

- **Decision**: Users with **< 30 days** of history get a cold-start projection blending their
  day-of-week averages with an anonymized population prior. The prior is computed by a
  **privileged periodic light-worker job** (`population_stats_job.py`) that aggregates across
  users into a global `population_stats` table with **no `user_id`** and no identifying fields.
  User-scoped request sessions never run cross-user aggregates.
- **Rationale**: DESIGN D + constitution Art. II (only a privileged job may aggregate
  cross-user; user sessions are RLS-bound). 30 days set in clarification.
- **Alternatives**: No cold-start (rejected — new users see an error/empty state); compute
  prior in a user session (rejected — Art. II violation).

## R6 — Detectors: anomaly + recurring

- **Decision**: Anomaly = robust z-score / IQR per (category) and per (merchant) flag PLUS a
  duplicate-charge rule (same merchant+amount within a short window). Recurring = group by
  merchant, detect regular cadence (weekly/monthly/…) and amount regularity, compute next
  expected charge, and flag a price increase when the amount steps up.
- **Rationale**: DESIGN D. Robust statistics (median/IQR) resist the outliers we're detecting;
  duplicate rule catches double-charges the statistical rule misses.
- **Alternatives**: Mean/stdev z-score (rejected — non-robust to the very outliers sought);
  ML anomaly models (overkill for v1).

## R7 — Invalidate-and-recompute on write; reads are DB reads

- **Decision**: On any write to a user's transactions (upload, form, future reclassify),
  enqueue a recompute job (`recompute_worker.py`) that recomputes that user's forecast,
  anomalies, and subscriptions and stores them. `get_forecast`/dashboard endpoints are plain
  DB reads of the stored derived rows.
- **Rationale**: Constitution Art. V — anything derived from transactions is invalidated on
  write, never time-expired. Keeps the read path fast and the forecast fresh.
- **Alternatives**: Compute on read (rejected — slow dashboard, repeated Prophet fits);
  time-based cache expiry (rejected — Art. V forbids for transaction-derived data).

## R8 — Transaction de-duplication

- **Decision**: Natural key `(user_id, date, amount, normalized_description)`; a row matching an
  existing key is skipped on insert. Normalization lowercases and trims the description.
- **Rationale**: Clarification 2026-06-16 — re-uploading or overlapping statements must not
  create divergent duplicate history; also underpins the duplicate-charge anomaly distinction
  (true duplicates vs. legitimate repeat purchases handled by the time-window rule, not dedup).
- **Alternatives**: Bank-provided transaction IDs (not present in CSV-class exports); hash of
  the whole row (equivalent but less legible).

## R9 — CI gate #2 on a committed golden fixture

- **Decision**: `backend/tests/golden/forecasting/` holds a committed fixture (synthetic
  multi-user history + expected horizon truth) via Git LFS. The gate computes forecaster MAE
  vs day-of-week baseline MAE on it and fails the build if forecaster MAE > baseline. CI never
  touches the live DB.
- **Rationale**: Constitution Art. V — CI-required artifacts are committed; CI is
  stack-independent. Acceptance criterion CI gate #2.
- **Alternatives**: Generate the fixture in CI (rejected — non-deterministic, and the gate
  must be reproducible).
