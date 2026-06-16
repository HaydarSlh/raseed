# Quickstart — Ingestion & Analytics (Phase 3 validation)

Runnable scenarios proving the phase's acceptance criteria. Contracts:
[http-api.md](./contracts/http-api.md), [internal-contracts.md](./contracts/internal-contracts.md).
Data shapes: [data-model.md](./data-model.md).

## Prerequisites
- The Phase-2 model-server is up and serving the pinned champion (`docker compose up -d
  modelserver`); migrations applied (`alembic upgrade head`).
- A signed-in test user (JWT) and the seed statement under `backend/tests/golden/`.

## Scenario 1 — Upload → categorized dashboard (US1, SC-001)
```bash
curl -s -X POST http://localhost:8000/uploads -H "Authorization: Bearer $JWT" \
  -F "file=@backend/tests/golden/seed_statement.csv"
# → {"ingested":N,"needs_review":k,"duplicates_skipped":0,"recompute_enqueued":true}
curl -s http://localhost:8000/dashboard -H "Authorization: Bearer $JWT" | jq '.transactions | length'
```
**Expect**: transactions listed with category + provenance + confidence; low-confidence rows
have `needs_review:true`.

## Scenario 2 — No raw bytes persisted (SC-003)
Run the integration test asserting that after an upload, no store (DB, MinIO, disk) contains
the raw file bytes:
```bash
pytest backend/tests/integration/test_no_raw_bytes_persist.py -q
```
**Expect**: pass — only enriched rows exist; the uploaded bytes appear nowhere.

## Scenario 3 — PAN/IBAN scrub (US1, FR-003)
Upload a statement containing a card/IBAN-like string and confirm stored descriptions are
scrubbed:
```bash
pytest backend/tests/unit/test_parsing_scrub.py -q
```
**Expect**: no PAN/IBAN substring survives into `transactions.description`.

## Scenario 4 — Projection with likely range + cold start (US2, SC-007)
```bash
curl -s http://localhost:8000/forecast -H "Authorization: Bearer $JWT" | jq '.points[0]'
# → {"date":"…","projected_balance":…,"lower":…,"upper":…}
```
**Expect**: 30 daily points each with lower<upper; a brand-new user (<30 days) returns
`is_cold_start:true` and still a full range (no error/empty state).

## Scenario 5 — CI gate #2: forecaster beats baseline (SC-002)
```bash
python backend/tests/golden/forecasting/run_gate.py
```
**Expect**: exit 0 — forecaster MAE ≤ day-of-week baseline MAE on the committed fixture; no DB
or compose stack started.

## Scenario 6 — Anomalies & subscriptions (US3)
With a seeded history containing an outlier, a duplicate charge, and a monthly subscription:
```bash
curl -s http://localhost:8000/anomalies -H "Authorization: Bearer $JWT" | jq
curl -s http://localhost:8000/subscriptions -H "Authorization: Bearer $JWT" | jq
```
**Expect**: the outlier and duplicate are flagged; the subscription lists cadence + next
charge; a stepped-up amount sets `price_increase:true`.

## Scenario 7 — Manual entry reuses the path + recompute (US4, SC-006)
```bash
curl -s -X POST http://localhost:8000/transactions -H "Authorization: Bearer $JWT" \
  -H 'content-type: application/json' \
  -d '{"txn_date":"2026-06-10","amount":-12.50,"description":"CASH LUNCH"}'
```
**Expect**: the row is categorized identically to an uploaded one; the next `/dashboard` read
reflects updated forecast/anomalies/subscriptions.

## Scenario 8 — Cross-user isolation (SC-005)
```bash
pytest backend/tests/integration/test_rls_isolation_phase3.py -q
```
**Expect**: user A never sees user B's transactions/forecast/anomalies; the only cross-user
aggregate is the anonymized `population_stats`, written solely by the privileged job.

## Acceptance roll-up
- US1: Scenarios 1–3.  US2: Scenarios 4–5.  US3: Scenario 6.  US4: Scenario 7.
- Cross-cutting: Scenario 8 (isolation), Scenario 5 (CI gate #2).
