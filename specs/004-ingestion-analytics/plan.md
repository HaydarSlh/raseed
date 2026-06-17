# Implementation Plan: Statement Ingestion & Financial Analytics

**Branch**: `004-ingestion-analytics` | **Date**: 2026-06-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/004-ingestion-analytics/spec.md`

## Summary

One shared ingestion service (in-memory parse → PAN/IBAN scrub → rules layer → model-server
call → confidence gate → store enriched rows) sits behind three entry points: the upload
page, the manual single-transaction form, and (later) the agent tool. New rows categorize
incrementally; the per-user forecaster, anomaly detector, and recurring detector recompute
over the updated history on write, and reads are plain DB lookups. A privileged light-worker
job computes an anonymized population prior used only for cold-start forecasts. Forecasting
decomposes known recurring cash-flow (projected deterministically) from variable
discretionary spend (the only part forecast), beats a day-of-week MAE baseline on a committed
golden fixture, and presents a likely range.

## Technical Context

**Language/Version**: Python 3.12 (backend, light worker), TypeScript/React (Vite SPA).

**Primary Dependencies**: FastAPI (async, layered), async SQLAlchemy + Alembic, Prophet
(forecaster, light-worker/back-of-request only — never in the serving image), numpy/pandas
for detectors, the Phase-2 model-server client (onnxruntime service, called over HTTP),
Redis + RQ (recompute jobs), fastapi-users (JWT), pgvector-enabled Postgres.

**Storage**: Postgres + per-user RLS (`app.user_id`). New tables: `transactions` (enriched),
`forecasts`, `anomalies`, `subscriptions`, and a global `population_stats` (no `user_id`,
written only by the privileged job). MinIO untouched (model artifacts only). Raw upload bytes
never persisted.

**Testing**: pytest (unit + integration with the Postgres service in CI), a committed golden
forecasting fixture under `backend/tests/golden/forecasting/`, Vitest for the SPA.

**Target Platform**: Linux containers via docker-compose; SPA in the browser.

**Project Type**: Web application (FastAPI backend + React SPA) plus a light worker.

**Performance Goals**: `get_forecast`/dashboard reads are DB reads (no model call on the read
path); ingestion categorizes incrementally; forecaster recompute runs off-request on the RQ
queue. Forecaster MAE ≤ day-of-week baseline on the fixture (CI gate #2).

**Constraints**: No raw file persistence; PAN/IBAN scrubbed in the parser; user-scoped
sessions never compute cross-user aggregates (only the privileged job does); derived data
invalidated and recomputed on write, never time-expired (constitution Art. V).

**Scale/Scope**: Single-user statements (hundreds–thousands of rows); 30-day projection
horizon; one ingestion function; one forecaster + two detectors; one upload page + dashboard.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Article | Compliance in this plan | Status |
|---------|-------------------------|--------|
| I. Layered, Async Architecture | Ingestion lives in `services/`; routers in `api/` never touch the DB; SQL only in `repositories/`; domain models in `domain/`. Model-server + DB calls awaited; independent reads (`asyncio.gather`). Recompute is an RQ job, not a blocking request path. | PASS |
| II. Isolation & Data Protection (NON-NEGOTIABLE) | `user_id` from JWT only; RLS on every new user table; raw bytes parsed in memory and discarded; PAN/IBAN scrubbed in the parser before any store. Population prior is anonymized, has no `user_id`, and is written only by the privileged job — user sessions never aggregate cross-user. Nothing user-level crosses to the LLM (no LLM in this phase). | PASS |
| III. ML Lifecycle Integrity | Provenance `rule \| model \| human` recorded per transaction; confidence gate routes low-confidence rows to `needs_review` (no auto-accept). Prophet runs in the light worker / off-request — **never in the lean model-server image** (no torch/transformers added to serving). No new model artifacts here; the Phase-2 ONNX champion is reused unchanged. | PASS |
| IV. Bounded Agent & Grounded RAG | No agent/LLM/RAG in this phase (explicitly out of scope). The agent tool entry point to ingestion is a future seam, noted but not built. | N/A (PASS) |
| V. Quality & Operations | CI gate #2 (forecaster MAE ≤ baseline) reads a committed golden fixture, never the live DB. Derived data invalidated on write. Decisions recorded in `DECISIONS.md`. Structured errors + request IDs reused from Phase 1. | PASS |

No violations — Complexity Tracking left empty.

## Project Structure

### Documentation (this feature)

```text
specs/004-ingestion-analytics/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (ingestion + HTTP + job contracts)
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── api/
│   │   ├── ingestion.py        # POST /uploads, POST /transactions (thin routers)
│   │   └── dashboard.py        # GET /dashboard, /forecast, /anomalies, /subscriptions
│   ├── services/
│   │   ├── ingestion.py        # the ONE ingestion function (parse→scrub→rules→model→gate→store)
│   │   ├── parsing.py          # in-memory statement parse + PAN/IBAN scrub
│   │   ├── rules.py            # merchant-lookup weak-supervision rules layer
│   │   ├── forecasting.py      # decomposition + Prophet + day-of-week baseline + cold start
│   │   ├── detectors.py        # anomaly (z/IQR + duplicate) + recurring detectors
│   │   └── recompute.py        # invalidate + enqueue recompute on write
│   ├── repositories/           # SQL only: transactions, forecasts, anomalies, subscriptions, population_stats
│   ├── domain/                 # Pydantic models + enums (provenance, anomaly type, cadence)
│   ├── workers/
│   │   ├── recompute_worker.py # RQ: recompute forecast/detectors for a user
│   │   └── population_stats_job.py  # PRIVILEGED periodic job → population_stats (no user_id)
│   └── infra/                  # model-server client (reused), redis/rq
├── migrations/                 # Alembic: new tables + RLS policies
└── tests/
    ├── unit/                   # parser scrub, rules, decomposition, detectors, cold start
    ├── integration/            # end-to-end ingest→dashboard, RLS isolation, no-raw-bytes
    └── golden/forecasting/     # COMMITTED fixture for CI gate #2

frontend/
└── src/
    ├── pages/                  # UploadPage, DashboardPage
    ├── components/             # TransactionList, ProjectionChart, AnomalyList, SubscriptionList
    └── services/               # API client for the new endpoints
```

**Structure Decision**: Web-application layout (existing `backend/` + `frontend/`), extending
the Phase-1 layered backend. The single ingestion function in `services/ingestion.py` is the
spine; entry points (`api/ingestion.py` upload + form, later the agent tool) all call it.
Forecaster/detectors live in `services/` but execute on the RQ queue via `workers/` so the
request path stays fast; the privileged population-stats job is a separate worker entry point
with no user RLS context.

## Complexity Tracking

> No constitution violations — no entries.
