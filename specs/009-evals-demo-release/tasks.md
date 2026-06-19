# Tasks: Evals, Demo & Release

**Input**: Design documents from `specs/009-evals-demo-release/`

**Organization**: Tasks grouped by user story. US1 (CI gates) is the critical path;
all other user stories can begin once US1 is complete. US3–US5 are largely independent.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to

---

## Phase 1: Setup

**Purpose**: Orient to existing state before implementing new tasks.

- [X] T001 Read `eval_thresholds.yaml`, `.github/workflows/ci.yml`, `scripts/smoke_compose.sh`, and `backend/tests/test_forecaster_gate.py` to confirm their current content before making any edits

---

## Phase 2: US1 — CI Gates All Green (Priority: P1) 🎯 MVP

**Goal**: All 8 CI gates pass. Gates 1–7 are stack-independent; Gate 8 is the compose
smoke test (exempted from the no-stack rule, `@pytest.mark.integration`).

**Independent Test**: `pytest backend/tests/test_forecaster_gate.py -q` passes;
`pytest backend/tests/test_compose_smoke.py -m integration -v` passes with Docker running;
the CI `backend` job shows Gate 2 in its step list.

**Current state (from codebase audit)**:
- Gate 1 (categorizer): ✅ `training/gate_holdout.py` + dedicated `categorizer-gate` CI job
- Gate 2 (forecaster): `backend/tests/test_forecaster_gate.py` exists but ❌ NOT in CI
- Gates 3–7: ✅ in CI backend job
- Gate 8 (compose smoke): `scripts/smoke_compose.sh` exists but ❌ no pytest wrapper, ❌ not in CI

- [X] T002 [US1] Add Gate 2 (forecaster) step to `.github/workflows/ci.yml` backend job, after Gate 3 step: `pytest tests/test_forecaster_gate.py -q` with `APP_ENV: local`
- [X] T003 [US1] Create `backend/tests/test_compose_smoke.py` — pytest wrapper for `scripts/smoke_compose.sh` marked `@pytest.mark.integration`; asserts script exits 0; after script completes, also asserts `GET http://localhost:5173` and `GET http://localhost:8000/health` return HTTP 200 (using `urllib.request`); imports `subprocess`, `pathlib.Path`, `pytest`, `urllib.request`
- [X] T004 [US1] Add Gate 8 CI job `compose-smoke` to `.github/workflows/ci.yml` after the `integration` job: `pytest tests/test_compose_smoke.py -m integration -v` with `needs: [backend]`; runs only on push to main
- [X] T005 [US1] Add measured-value annotation comments to `eval_thresholds.yaml` for Gate 1 (measured macro_f1 = 0.8934 from model card) and Gate 2 (beat_baseline = true; add `last_measured_forecaster_mae` comment); add Gate 8 `last_measured: "CI skipped when Docker unavailable"` note under `compose_smoke`

**Checkpoint**: All 8 gates now have CI representation. `pytest backend/tests/test_forecaster_gate.py` passes locally.

---

## Phase 3: US2 — Demo Seed & Rehearsal (Priority: P2)

**Goal**: `scripts/seed_demo.py` creates 2 demo users with 6 months of realistic UK
transactions. `backend/scripts/simulate_drift.py` is documented for rehearsal.

**Independent Test**: `python scripts/seed_demo.py` exits 0 and prints "Seeded 2 demo
users"; re-running is idempotent.

- [X] T006 [US2] Create `scripts/seed_demo.py` — async script using `asyncio.run()` + SQLAlchemy `AsyncSession`; constructs its own `AsyncEngine` from `DATABASE_URL` environment variable (do NOT import from `backend/app/` package — use `sqlalchemy.ext.asyncio.create_async_engine` directly); creates `demo@raseed.app` and `demo2@raseed.app` with argon2-hashed passwords "Demo1234!" and "Demo5678!" respectively using `passlib.hash.argon2`; inserts ~180 transactions per user over 6 months with UK-realistic merchants (Tesco, Sainsbury's, Amazon, TfL, HMRC, etc.), GBP amounts, 18-class Phase-2 categories, type codes (DEB/BP/DD/FPI/BGC), `label_source='human'`, `needs_review=False`; uses `INSERT … ON CONFLICT (email) DO NOTHING` for users and natural-key dedup for transactions; prints summary on completion
- [X] T007 [P] [US2] Add `scripts/README.md` (one paragraph) explaining `seed_demo.py` usage and pointing to `backend/scripts/simulate_drift.py` for the drift rehearsal demo

**Checkpoint**: Demo users are seeded with realistic history. Drift rehearsal procedure is documented.

---

## Phase 4: US3 — Finalized Documentation (Priority: P3)

**Goal**: All 5 documentation files exist and cover their required sections.

**Independent Test**: The Scenario 5 quickstart validation script passes (all section
headings present in all required files).

- [X] T008 [P] [US3] Complete `docs/DESIGN.md` — replace the three `_Deferred to Phase X_` placeholder lines with concise paragraphs: (1) Scaling story: per-user Prophet O(1) cost, pgvector IVFFlat index at scale, stateless FastAPI horizontal scaling, Redis session fan-out; (2) Isolation & erasure: RLS enforcement mechanics, Phase-6 right-to-erasure purge order, model-unlearning limitation documented in SECURITY.md; (3) ML lifecycle: champion/challenger gate flow, drift signals (mean confidence, correction rate, PSI, new-merchant rate), retrain cadence, Slack webhook ops-only signals
- [X] T009 [P] [US3] Create `docs/EVALS.md` — Markdown table with columns: Gate | Description | Threshold Key | Committed Value | Last Measured | Notes; 8 rows (Gates 1–8); RAG rows include FakeEmbedder footnote; Gate 8 row notes `[integration]` skip when Docker unavailable; Gate 1 row shows 0.8934 measured; Gate 2 row shows beat_baseline=true
- [X] T010 [P] [US3] Create `docs/RUNBOOK.md` — 5 sections: `## Startup` (docker compose commands, health check URLs), `## Secret rotation` (Vault path, env var reload), `## Retraining` (how to trigger and monitor RQ retrain job, champion/challenger gate commands), `## Erasure` (how to invoke `DELETE /users/me/erasure`, verify erasure_audit), `## Alert response` (Slack drift alert → inspect → simulate_drift.py → promote or block)
- [X] T011 [US3] Append D16–D20 to `docs/DECISIONS.md` — 5 rows: D16 (Gate 1 CI strategy: ONNX Runtime on holdout, stack-independent), D17 (Gate 8 @integration exemption), D18 (RAG 0.0 threshold FakeEmbedder rationale), D19 (seed_demo.py direct AsyncSession vs HTTP API), D20 (v0.1.0 tag cut after gates green)

**Checkpoint**: All docs complete. Scenario 5 quickstart script passes.

---

## Phase 5: US4 — Fresh-Clone Demo (Priority: P4)

**Goal**: Fresh clone → `cp .env.example .env` → `docker compose up` → working demo.

**Independent Test**: `docker compose up` starts all services. `http://localhost:5173`
loads and demo@raseed.app can log in.

- [X] T012 [P] [US4] Read `docker-compose.yml` and verify all default (non-training) services have `healthcheck` entries; add any missing healthchecks (postgres, redis, backend, frontend, modelserver at minimum); verify `.env.example` contains all required variables with safe placeholder values
- [X] T013 [P] [US4] Add `## Demo` section to `README.md` with 3-command quickstart (`git clone`, `cp .env.example .env`, `docker compose up`), demo login credentials (demo@raseed.app / Demo1234!), and link to `docs/RUNBOOK.md`

**Checkpoint**: Anyone can run the 3-command quickstart and reach the demo UI.

---

## Phase 6: US5 — Release Tag (Priority: P5)

**Goal**: `README.md` submission block filled; `v0.1.0` tag on main.

**Independent Test**: `git tag -l v0.1.0` returns `v0.1.0`; README has no "TBD" placeholders in the submission block.

- [X] T014 [US5] Fill `README.md` submission block — add or update `## Evaluation Results` section with a table of all 8 gates: gate name, committed threshold, measured value (from `eval_thresholds.yaml` and the model card); no TBD placeholders
- [X] T015 [US5] Update graphify knowledge graph: run `graphify update .` from repo root and verify `graphify-out/graph.json` is updated (background rebuild triggered by git hooks is fine; confirm the log at `~/.cache/graphify-rebuild.log` shows success)

**Note**: The `v0.1.0` git tag is created manually by the user after all gates are confirmed green on main — it is not automated by the implementation tasks.

**Checkpoint**: Documentation and eval results are complete; graphify is fresh.

---

## Phase 7: Polish & Validation

**Purpose**: Final validation pass.

- [X] T016 Run quickstart.md Scenario 1 (stack-independent gates): `cd backend && pytest tests/test_categorizer_gate.py tests/test_forecaster_gate.py tests/test_tool_selection_gate.py tests/test_rag_gate.py tests/test_redteam_gate.py tests/test_secret_scan_gate.py tests/test_drift_gate.py -v` and confirm all PASS
- [X] T017 [P] Run quickstart.md Scenario 5 (documentation completeness): the inline Python check script and confirm all 5 files print `OK:`
- [X] T018 [P] Run quickstart.md Scenario 6 (README submission block): Python one-liner check passes with no TBD detected
- [X] T019 [P] Verify SECURITY.md completeness: assert all 4 required sections exist (`## Secret Management`, `## PII Redaction Boundary`, `## Model Unlearning Limitation`, `## Reporting a Vulnerability`) and file is non-empty (covers FR-019)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup/Read)**: No dependencies — start immediately
- **Phase 2 (US1 CI gates)**: Depends on Phase 1 orientation
- **Phases 3–6**: Independent of each other; can run in parallel after Phase 1
- **Phase 7 (Validation)**: Depends on Phases 2–6 complete

### Within US1

- T002 (Gate 2 CI): can run independently of T003/T004
- T003 (test_compose_smoke.py): must complete before T004
- T004 (Gate 8 CI job): depends on T003
- T005 (eval_thresholds.yaml annotations): independent

### Parallel Opportunities

```bash
# US3 documentation tasks can all run in parallel (different files):
Task T008: docs/DESIGN.md
Task T009: docs/EVALS.md
Task T010: docs/RUNBOOK.md

# US4 tasks are independent:
Task T012: docker-compose.yml + .env.example
Task T013: README.md Demo section

# Phase 7 validation tasks are independent:
Task T017: doc completeness check
Task T018: README submission check
```

---

## Implementation Strategy

### MVP First (US1 Only)

1. T001: Orient to current state
2. T002–T005: Wire missing gates into CI
3. **STOP**: Confirm all 8 gates have CI representation
4. Proceed to US2–US5 in parallel

### Full Delivery

1. T001 → T002–T005 (US1) → CI gates all wired
2. T006–T007 (US2), T008–T011 (US3), T012–T013 (US4) in parallel
3. T014–T015 (US5)
4. T016–T018 (validation)
5. User cuts `v0.1.0` tag after confirming all gates green on main

---

## Notes

- Gate 1 (`training/gate_holdout.py`) and its CI job already exist — do NOT create a duplicate `test_categorizer_gate.py`
- `backend/scripts/simulate_drift.py` already exists — no code changes needed, only documentation
- The v0.1.0 tag is a user action, not an automated task — it comes AFTER the user tests the app
- `[P]` tasks operate on different files and have no dependencies on incomplete tasks
