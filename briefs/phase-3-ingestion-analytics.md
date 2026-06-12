# Phase 3 — Ingestion & analytics

## Intent
A user uploads a statement and lands on a dashboard showing categorized
transactions, a projected balance with a likely range, anomalies, and
subscriptions.

## In scope (deliverables)
- The single shared ingestion service: in-memory parse (raw file discarded),
  PAN/IBAN scrub in the parser, rules layer (merchant lookup, provenance=rule,
  confidence 1.0), model-server call, confidence gate (above threshold ->
  provenance=model; below -> `needs_review`), store enriched rows.
- Manual single-transaction form using the same service function.
- Prophet per-user forecaster on the decomposition (recurring projected
  deterministically; only variable discretionary spend is forecast); day-of-week
  baseline it must beat; cold-start fallback blending day-of-week averages with
  the population prior. v1 assumes recurring income (variable income = future).
- The privileged stats job on the LIGHT worker computing the anonymized
  population prior into a global stats table (user-scoped sessions must not
  compute cross-user aggregates).
- Anomaly detector (robust z-score/IQR per category & merchant + duplicate
  rule); recurring detector (cadence, next charge, price-increase flags).
- Invalidate-and-recompute derived data on write; `get_forecast` is a DB read.
- Upload page + dashboard UI (transactions, projection + range, anomalies,
  subscriptions).

## Out of scope
Chat/agent, review-queue UI (Phase 5), RAG.

## Acceptance criteria
- End-to-end on seed data: upload -> categorized -> dashboard populated.
- CI gate #2: forecaster MAE <= baseline, computed on a COMMITTED fixture
  dataset under `tests/golden/forecasting/` (CI never needs the live DB).
- A test proves no raw upload bytes persist in any store.
- Low-confidence rows visibly carry `needs_review`.

## Notes for /plan
One ingestion function, multiple entry points (upload, form, later the agent
tool). New rows categorize incrementally; forecast/aggregates recompute over
updated history.
