# Quickstart: Dashboard UI

Validation guide proving the SPA works end-to-end against the running backend. For
field shapes see [contracts/ui-api-contract.md](./contracts/ui-api-contract.md); for view
models see [data-model.md](./data-model.md).

## Prerequisites

- The Phase 3 stack is up: `docker compose up -d postgres redis minio vault modelserver
  backend worker frontend` (backend on `:8000`, frontend on `:5173`, model-server on
  `:8080`).
- Migrations applied through `0003_ingestion_analytics` (`docker compose run --rm migrate`).
- A statement CSV with > 30 days of history available (e.g. derived from
  `backend/tests/golden/forecasting/history.parquet`, or any `Date,Amount,Description`
  CSV spanning a month).

## Setup

```bash
cd frontend
npm install          # pulls react-router-dom, recharts, tailwindcss, vitest, RTL
npm run dev          # serves http://localhost:5173
```

## Automated gates (stack-independent — these are the CI gates)

```bash
cd frontend
npm run typecheck    # tsc --noEmit — zero errors
npm run lint         # eslint --max-warnings 0 — zero warnings
npm run test         # vitest run — component/behaviour tests pass
```

Expected: all three exit 0. These never start the compose stack (constitution Art. V).

## Scenario 1 — Auth guard (FR-001)

1. With no token (clear `localStorage`), visit `http://localhost:5173/dashboard`.
2. **Expected**: redirected to `/login`.
3. Sign in (register first at `/register` if needed). **Expected**: reaching `/dashboard`
   now succeeds.

## Scenario 2 — Upload → populated dashboard (US1, SC-001)

1. Go to `/upload`, choose the statement CSV, submit.
2. **Expected**: a result banner like "5 imported, 4 flagged for review", then navigation
   to `/dashboard`.
3. **Expected**: the transaction list shows the uploaded rows, newest first, each with a
   category badge and a `rule`/`model` source chip; no page refresh was needed.

## Scenario 3 — Forecast chart vs cold-start (US2, SC-002, SC-005)

1. With > 30 days of history uploaded, view the dashboard forecast panel.
2. **Expected**: a line chart of projected balance with ≥ 1 point (`is_cold_start=false`).
3. On a fresh account with < 30 days, **Expected**: a "not enough history yet" notice,
   never a broken/empty chart.

## Scenario 4 — Anomalies & subscriptions (US2)

1. After recompute completes (a few seconds), use the forecast/dashboard **Refresh**.
2. **Expected**: any anomalous transactions appear in the anomalies panel labeled by type
   and are highlighted in the main list; detected subscriptions appear as cards with
   merchant, cadence, typical amount, and a "price increased" badge where applicable.

## Scenario 5 — Review status & read-only category (US3, SC-003, SC-004, FR-012)

1. Inspect a transaction the model was unsure about.
2. **Expected**: it carries a distinct needs-review indicator; its source chip shows
   `model` vs `rule`.
3. Click the category badge. **Expected**: nothing editable — the category is read-only
   (correction is a Phase 5 feature). No `POST /corrections` call is made.

## Scenario 6 — Manual entry (US4)

1. On `/upload`, fill the manual form (date, amount, description); try submitting with a
   blank field. **Expected**: submit is disabled until all required fields are present.
2. Submit a valid entry. **Expected**: navigation to `/dashboard`; the new transaction
   appears with a category.
3. Submit the same entry again. **Expected**: a readable "already recorded" message
   (backend `409`), no crash.

## Scenario 7 — Empty state & error handling (FR-013, FR-014, SC-007)

1. Brand-new account, no transactions: **Expected** an inviting empty state inviting an
   upload — not blank/broken panels.
2. Stop the backend (`docker compose stop backend`) and load `/dashboard`. **Expected**: a
   readable error with a retry affordance, not a frozen/blank screen.

## Acceptance roll-up

| Spec item | Scenario |
|-----------|----------|
| FR-001 auth guard | 1 |
| US1 / SC-001 upload→dashboard | 2 |
| US2 / SC-002 forecast | 3 |
| SC-005 cold-start | 3 |
| US2 anomalies/subscriptions | 4 |
| US3 / SC-003 / SC-004 review status, read-only category | 5 |
| FR-012 no edit control | 5 |
| US4 manual entry | 6 |
| FR-013 / FR-014 / SC-007 empty + errors | 7 |
| SC-006 typecheck/lint/test | Automated gates |
