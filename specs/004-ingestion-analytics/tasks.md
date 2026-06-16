# Tasks: Statement Ingestion & Financial Analytics

**Feature**: `004-ingestion-analytics` | **Plan**: [plan.md](./plan.md) | **Spec**: [spec.md](./spec.md)

Tasks are organized by user story (spec priorities P1–P3). Tests are included where the spec
mandates them (no-raw-bytes proof, CI gate #2, RLS isolation). `[P]` = parallelizable
(different files, no incomplete dependency). Story labels: [US1] upload→dashboard,
[US2] projection, [US3] anomalies/subscriptions, [US4] manual entry.

## Phase 1: Setup

- [x] T001 Add Phase-3 deps (prophet, pandas, numpy) to `backend/pyproject.toml` under a worker/analytics extra — NOT to the model-server image (constitution Art. III). Keep `backend/[dev]` test tools.
- [x] T002 [P] Create the committed fixture directory `backend/tests/golden/forecasting/` with a README describing the fixture schema (multi-user synthetic history + horizon truth).
- [x] T003 [P] Register the `forecaster` gate block scaffold in `eval_thresholds.yaml` (keys `mae_max`, baseline-beat) — values filled in T040.

## Phase 2: Foundational (blocking prerequisites)

- [x] T004 Add domain enums in `backend/app/domain/enums.py`: `Provenance`, `AnomalyType`, `Cadence`.
- [x] T005 [P] Add Pydantic domain models in `backend/app/domain/transactions.py` (ParsedRow, EnrichedTransaction, IngestResult) per data-model.md.
- [x] T006 [P] Add Pydantic domain models in `backend/app/domain/analytics.py` (Forecast, ForecastPoint, Anomaly, Subscription, PopulationStat).
- [x] T007 Alembic migration in `backend/migrations/` creating `transactions`, `forecasts`, `anomalies`, `subscriptions` (user-scoped) + `population_stats` (no user_id), with the dedup unique index `(user_id, txn_date, amount, normalized_description)`.
- [x] T008 Add RLS policies in the same migration for all user-scoped tables keyed on `app.user_id`; `population_stats` gets NO RLS (global, read-only to sessions). Verify reset-on-release reused from Phase 1.
- [x] T009 [P] Repository `backend/app/repositories/transactions_repo.py` (insert-skip-on-conflict, list by user, set is_anomaly).
- [x] T010 [P] Repositories `backend/app/repositories/analytics_repo.py` (replace+read forecasts/anomalies/subscriptions) and `population_stats_repo.py` (privileged write, session read).
- [x] T011 Wire an RQ recompute queue + enqueue helper in `backend/app/infra/queue.py` (reuse Phase-1 Redis/RQ).
- [x] T012 Confirm the model-server client in `backend/app/infra/` exposes a batched `classify(descriptions)` call; add if missing (awaited httpx, no torch).

## Phase 3: User Story 1 — Upload → categorized dashboard (P1) 🎯 MVP

**Goal**: Upload a statement and see categorized transactions, low-confidence rows flagged.
**Independent test**: Upload seed statement → `/dashboard` lists categorized transactions with provenance/confidence; `needs_review` visible; no raw bytes persisted.

- [x] T013 [US1] In-memory parser + PAN/IBAN scrub in `backend/app/services/parsing.py` (CSV-class; yields ParsedRow; regex-scrubs card/IBAN before return; never writes bytes).
- [x] T014 [P] [US1] Rules layer in `backend/app/services/rules.py` (merchant lookup → category, provenance=rule, confidence 1.0).
- [x] T015 [US1] The single `ingest_transactions(user_id, rows)` in `backend/app/services/ingestion.py`: dedup → rules → model-server → confidence gate (reuse per-category `operating_thresholds`) → persist. Depends on T013–T014, T009, T012.
- [x] T016 [US1] Confidence-gate helper reading `eval_thresholds.yaml` `categorizer.operating_thresholds` in `backend/app/services/ingestion.py` (`always_review` / below-threshold → needs_review).
- [x] T017 [US1] Upload router `POST /uploads` in `backend/app/api/ingestion.py` (multipart → parse → ingest → enqueue recompute). Thin; no SQL.
- [x] T018 [US1] `GET /dashboard` in `backend/app/api/analytics.py` returning transactions (forecast/anomalies/subscriptions empty until later stories); independent reads via `asyncio.gather`.
- [ ] T019 [P] [US1] Frontend `UploadPage` + `TransactionList` (category, provenance, confidence, `needs_review` badge) in `frontend/src/`. **[DEFERRED — backend only scope]**
- [x] T020 [US1] Unit test `backend/tests/test_parsing.py` — PAN/IBAN scrubbed (FR-003).
- [x] T021 [US1] Integration test `backend/tests/integration/test_no_raw_bytes_persist.py` — after upload, no store holds raw bytes (SC-003).
- [x] T022 [US1] Unit test `backend/tests/test_ingestion.py` — below-threshold → needs_review; rule match → provenance=rule (FR-004/006).

**Checkpoint**: MVP — upload to categorized dashboard works end-to-end.

## Phase 4: User Story 2 — Projection with likely range (P2)

**Goal**: Dashboard shows a 30-day projected balance with a likely range; cold start for new users.
**Independent test**: Seeded history → `/forecast` returns 30 points with lower<upper; <30-day user → `is_cold_start:true` with a full range; forecaster beats day-of-week baseline on the fixture.

- [x] T023 [US2] Decomposition + forecasting in `backend/app/services/analytics.py` (cold-start dow-avg + Prophet path; `compute_forecast()`, `detect_anomalies()`, `detect_subscriptions()`).
- [x] T024 [US2] Day-of-week baseline `_day_of_week_baseline()` in `backend/app/services/analytics.py` (the value to beat).
- [x] T025 [US2] Prophet discretionary forecast (native intervals → likely range), 30 daily points, in `backend/app/services/analytics.py`. Prophet imported only here / worker — never in serving.
- [x] T026 [US2] Cold-start fallback (<30 days history): dow-avg projection, `is_cold_start=true`.
- [x] T027 [US2] Privileged `backend/workers/stats.py` — periodic, no RLS user context, aggregates anonymized `population_stats` with k-anonymity min-user guard; never request-invoked.
- [x] T028 [US2] Recompute worker `backend/workers/recompute.py` computing+replacing the user's forecast, anomalies, subscriptions on write.
- [x] T029 [US2] `GET /forecast` in `backend/app/api/analytics.py` (DB read) + `/dashboard` includes forecast block.
- [ ] T030 [P] [US2] Frontend `ProjectionChart` (point + shaded likely range; cold-start indicator) in `frontend/src/`. **[DEFERRED — backend only scope]**
- [x] T031 [US2] Built committed golden fixture `backend/tests/golden/forecasting/history.parquet` + `expected_horizon.parquet` + generate_fixture.py + CI gate test `backend/tests/test_forecaster_gate.py`.
- [x] T032 [US2] Unit tests in `backend/tests/test_analytics.py` — anomaly detection, subscription detection, forecaster cold-start path.

**Checkpoint**: Projection with range renders; CI gate #2 runnable locally.

## Phase 5: User Story 3 — Anomalies & subscriptions (P3)

**Goal**: Dashboard flags outliers/duplicates and lists subscriptions with cadence/next charge/price-increase.
**Independent test**: Seeded outlier+duplicate+monthly sub → `/anomalies` flags outlier & duplicate; `/subscriptions` lists cadence + next charge; stepped amount → price_increase.

- [x] T033 [US3] Anomaly detector in `backend/app/services/analytics.py` (robust IQR per category & merchant + duplicate-charge rule within a short window).
- [x] T034 [US3] Recurring detector in `backend/app/services/analytics.py` (cadence + amount regularity, next charge, price-increase flag).
- [x] T035 [US3] `recompute.py` computes+replaces anomalies & subscriptions and sets `transactions.is_anomaly`.
- [x] T036 [US3] `GET /anomalies` and `GET /subscriptions` (DB reads) + `/dashboard` extended; in `backend/app/api/analytics.py`.
- [ ] T037 [P] [US3] Frontend `AnomalyList` + `SubscriptionList` components in `frontend/src/`. **[DEFERRED — backend only scope]**
- [x] T038 [US3] Unit tests in `backend/tests/test_analytics.py` — outlier, duplicate, cadence, price-increase.

## Phase 6: User Story 4 — Manual single-transaction entry (P3)

**Goal**: A form adds one transaction through the same ingestion path; derived views recompute.
**Independent test**: POST one transaction → appears categorized identically; next dashboard read reflects updated forecast/anomalies/subscriptions.

- [x] T039 [US4] `POST /transactions` in `backend/app/api/ingestion.py` (one row → `ingest_transactions` → enqueue recompute). Frontend form deferred per scope.
- [ ] T040 [US4] Integration test `backend/tests/integration/test_manual_entry_recompute.py` — manual row categorized via same path; recompute reflects it (SC-006).

## Phase 7: Polish & Cross-Cutting

- [x] T041 Fill `eval_thresholds.yaml` `forecaster` (beat_baseline: true) from the fixture gate design; CI gate #2 test lives in `backend/tests/test_forecaster_gate.py`.
- [x] T042 [P] Integration test `backend/tests/integration/test_rls_isolation_phase3.py` — cross-user isolation across all new tables; population_stats is the only cross-user aggregate (SC-005).
- [x] T043 [P] Appended `docs/DECISIONS.md` — decomposition rule, 30-day horizon, cold-start cutoff, dedup natural key, k-anonymity guard, Prophet-off-serving placement, IQR anomaly, recurring cadence.
- [ ] T044 Run `quickstart.md` scenarios 1–8 against the built stack + committed fixture; confirm acceptance criteria.
- [x] T045 [P] `ruff` green for all new `backend/` files; B008 added to ignore list (FastAPI pattern).
- [ ] T046 Refresh the knowledge graph: `graphify update .`.

## Dependencies & Order

- **Setup (P1)** → **Foundational (P2)** block everything.
- **US1 (P1)** is the MVP and depends only on Foundational.
- **US2 (P2)** depends on Foundational + US1 (needs stored transactions); introduces the recompute worker + population job.
- **US3 (P3)** depends on US2's recompute worker (extends it) and US1's transactions.
- **US4 (P3)** depends on US1's `ingest_transactions`; recompute reuse from US2/US3.
- **Polish** last.

## Parallel Opportunities

- Setup: T002, T003 [P].
- Foundational: T005, T006 [P]; T009, T010 [P] after migration.
- US1: T014 [P] (rules) alongside T013 (parser); T019 [P] (UI) alongside services.
- US2: T030 [P] (UI) alongside services.
- US3: T037 [P] (UI). Polish: T042, T043, T045 [P].

## MVP Scope

**User Story 1 alone** (Phases 1–3) is a shippable MVP: upload a statement → categorized
transactions on a dashboard with `needs_review` flagging and the no-raw-bytes guarantee.
