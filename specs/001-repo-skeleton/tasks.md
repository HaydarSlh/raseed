---
description: "Task list for Phase 0 — Repository Skeleton & Project Map"
---

# Tasks: Repository Skeleton & Project Map

**Input**: Design documents from `specs/001-repo-skeleton/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Phase 0 ships only a boot/import smoke check and the lint + type-check CI
gate (per brief and `docs/PLAN.md`). No TDD test-first phase is generated; full CI
gates (categorizer F1, forecaster MAE, compose smoke, etc.) arrive in later phases.

**Organization**: Tasks are grouped by user story. Setup and Foundational build the
shared skeleton (every created file carries a single-responsibility header comment —
this is a global convention, FR-002); the user-story phases deliver the three
independently testable outcomes: the stack boots (US1), the map is navigable (US2),
and CI is green (US3).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Every file-creation task MUST add a one-line header comment stating the file's
  single responsibility (docstring for `.py`; leading comment for TS/YAML/Dockerfiles).

## Path Conventions

Multi-service monorepo per plan.md: `backend/`, `modelserver/`, `trainer/`,
`frontend/`, plus repo-root orchestration/config. Paths below are repo-relative.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Repository-wide scaffolding every service and story depends on.

- [ ] T001 Create the full agreed top-level tree with `.gitkeep` where empty: `backend/app/{core,api,services,repositories,domain,infra,workers}`, `backend/{alembic/versions,prompts,tests/{unit,golden,redteam}}`, `modelserver/`, `trainer/`, `training/notebooks/`, `frontend/src/{pages,components,api}`, `rag-corpus/`, `scripts/`, `docs/`, `.github/workflows/`
- [ ] T002 [P] Create `.gitignore` (venvs, `node_modules/`, `dist/`, `graphify-out/`, `training/data/`, `.env`) and `.gitattributes` initializing Git LFS tracking for model artifacts, fixtures, and the frozen holdout
- [ ] T003 [P] Create `.graphifyignore` (`node_modules/`, `graphify-out/`, `training/data/`, venvs, `dist/`)
- [ ] T004 [P] Create `.env.example` at repo root with every variable needed to boot the default stack (DB, Redis, MinIO, Vault, service ports) with safe local defaults — copy to `.env` is sufficient (FR-006)
- [ ] T005 [P] Create `eval_thresholds.yaml` at repo root with placeholder thresholds for the 8 CI gates (FR-009)
- [ ] T006 [P] Create `docs/DECISIONS.md` and `docs/DESIGN.md` placeholders with header comments (scaling/erasure notes deferred to later phases)

**Checkpoint**: Tree and root scaffolding exist; nothing boots yet.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Per-service code skeletons that import cleanly, boot empty, and carry
header comments. **Blocks all three user stories** — US1 needs bootable services,
US2 needs the files to audit, US3 needs the tooling configs.

**⚠️ CRITICAL**: No user story work begins until this phase is complete.

### Backend (layered per constitution Article I)

- [ ] T007 Create `backend/pyproject.toml` — deps (FastAPI, uvicorn, async SQLAlchemy, pydantic-settings, structlog, httpx, tenacity, RQ, alembic) + ruff + mypy config, Python 3.12
- [ ] T008 [P] Create `backend/app/core/config.py` — single `Settings` (pydantic-settings, `extra='forbid'`, fail-fast on missing required values)
- [ ] T009 [P] Create `backend/app/core/logging.py` — structlog JSON config with request-id support
- [ ] T010 [P] Create `backend/app/core/exceptions.py` — domain exception hierarchy mapped to structured HTTP errors
- [ ] T011 Create `backend/app/core/lifespan.py` — lifespan context constructing stub singletons (db engine, redis, minio, vault, llm adapter, modelserver client) (depends on T008, T009)
- [ ] T012 [P] Create `backend/app/infra/` adapter stubs (`db.py`, `redis.py`, `minio.py`, `vault.py`, `llm.py`, `modelserver_client.py`) — header comments + signatures only, no logic
- [ ] T013 [P] Create package stubs for `backend/app/api/`, `backend/app/services/`, `backend/app/repositories/`, `backend/app/domain/` (`__init__.py` + a header-only placeholder module each) — no endpoints, models, or business logic (FR-012)
- [ ] T014 Create `backend/main.py` — FastAPI app factory wiring lifespan + a `/healthz` route; boots with no business endpoints (depends on T008–T013)
- [ ] T015 [P] Create `backend/app/workers/` entrypoint stubs (`stats.py`, `drift.py`, `slack_webhook.py`) + a worker bootstrap that connects to RQ (header comments; ops-signals-only note)
- [ ] T016 [P] Create `backend/alembic/env.py`, `backend/alembic.ini`, and an empty baseline revision in `backend/alembic/versions/`
- [ ] T017 [P] Create `backend/Dockerfile` (`python:3.12-slim`, installs backend; used by `backend`, `worker`, and `migrate`)
- [ ] T018 [P] Create `backend/tests/unit/test_app_boot.py` — import/boot smoke test asserting the app factory builds and `/healthz` is registered (no stack needed)
- [ ] T019 [P] Create `backend/prompts/.gitkeep` with a header note that prompts are version-controlled files (Article IV)

### model-server (lean, no torch)

- [ ] T020 [P] Create `modelserver/app.py` — FastAPI `/healthz` returning `{"status":"ok","model":"none","detail":"no model loaded"}`; no hash guard (contracts/modelserver-healthz.md)
- [ ] T021 [P] Create `modelserver/pyproject.toml` (fastapi, uvicorn, onnxruntime, numpy — **no torch**) and `modelserver/Dockerfile` (lean)

### trainer (heavy, profile-gated)

- [ ] T022 [P] Create `trainer/train.py` entrypoint stub, `trainer/pyproject.toml` (torch, transformers), and `trainer/Dockerfile` — built only under the `training` compose profile, never on a request path
- [ ] T023 [P] Create `training/notebooks/README.md` placeholder for Colab foundation-training notebooks (header comment)

### frontend (React + Vite)

- [ ] T024 [P] Create `frontend/package.json`, `frontend/tsconfig.json`, `frontend/vite.config.ts` (React 18, Vite 5, Node 20; scripts: `dev`, `build`, `typecheck`, `lint`)
- [ ] T025 [P] Create `frontend/index.html` and `frontend/src/{main.tsx, App.tsx}` + `pages/`, `components/`, `api/` stubs with header comments (minimal app that renders)
- [ ] T026 [P] Create `frontend/Dockerfile`

**Checkpoint**: Every service has bootable, import-clean code with header comments.

---

## Phase 3: User Story 1 - Fresh clone boots the whole stack empty (Priority: P1) 🎯 MVP

**Goal**: `cp .env.example .env` → `docker compose up` brings every default service
to healthy; model-server reports "no model loaded"; trainer stays off the default
boot; migrate runs once and exits.

**Independent Test**: Run quickstart Scenarios 1–3 and 6 — confirm all default
services healthy, `trainer` absent, modelserver `/healthz` reports "no model
loaded", and a missing `.env` fails clearly.

- [ ] T027 [US1] Create `docker-compose.yml` with services `postgres` (pgvector), `redis`, `minio`, `vault`, `migrate`, `backend`, `modelserver`, `worker`, `frontend`, `trainer`; services address peers by service name (no localhost); `trainer` set to `profiles: ["training"]` (contracts/compose-services.md)
- [ ] T028 [US1] Add named volumes `pgdata`, `redisdata`, `miniodata` and attach to `postgres`, `redis`, `minio` (FR-005); no service persists raw user files (Article II)
- [ ] T029 [P] [US1] Add healthchecks for all default services (`pg_isready`, `redis-cli ping`, MinIO `/minio/health/live`, `vault status`, backend & modelserver `/healthz`, frontend index) (R2)
- [ ] T030 [US1] Configure `migrate` as a one-shot service (`restart: "no"`) running `alembic upgrade head` then exiting; `backend` `depends_on` migrate `service_completed_successfully` and infra `service_healthy` (depends on T027, T029)
- [ ] T031 [US1] Wire `.env`/compose `env_file` so the default stack boots from a copied `.env`; ensure a missing `.env` produces a clear, actionable failure (edge case)
- [ ] T032 [US1] Create `scripts/smoke_compose.sh` — bring up the default stack, assert all default services healthy and `trainer` absent (scaffold for CI gate 8; not wired into CI this phase)

**Checkpoint**: The empty stack boots from a fresh clone — MVP delivered.

---

## Phase 4: User Story 2 - Navigable project map (Priority: P2)

**Goal**: Every stub file carries a single-responsibility header comment and the
knowledge graph resolves a responsibility to its path.

**Independent Test**: Run quickstart Scenario 4 — open arbitrary stubs to confirm
header comments, then `graphify query "where does ingestion live"` returns the
correct path.

- [ ] T033 [P] [US2] Create `rag-corpus/.gitkeep` and `scripts/.gitkeep` placeholders with header comments describing each area's responsibility
- [ ] T034 [US2] Sweep the whole tree and ensure 100% of stub files begin with a single-responsibility header comment; add any missing ones (FR-002, SC-002)
- [ ] T035 [US2] Run `graphify update .` to regenerate the knowledge graph from the skeleton
- [ ] T036 [US2] Verify `graphify query "where does ingestion live"` resolves to the correct ingestion path (SC-005); record the result in quickstart notes if useful

**Checkpoint**: Project map complete and navigable.

---

## Phase 5: User Story 3 - CI green on lint + type-check (Priority: P3)

**Goal**: Lint and type-check pass on the empty skeleton, independent of the running
stack.

**Independent Test**: Run quickstart Scenario 5 — `ruff` + `mypy` (backend) and
`tsc` + `eslint` (frontend) pass locally; the GitHub Actions workflow is green and
never starts compose.

- [ ] T037 [P] [US3] Create `frontend/.eslintrc.*` and ensure `typecheck`/`lint` npm scripts run cleanly on the stub app
- [ ] T038 [US3] Create `.github/workflows/ci.yml` — jobs: backend (`ruff check` + `mypy`) and frontend (`tsc --noEmit` + `eslint`); installs deps only, never starts the compose stack (FR-008, Article V)
- [ ] T039 [US3] Run backend `ruff check . && mypy .` and frontend `npm run typecheck && npm run lint` locally; fix any stub that fails so the skeleton is green (SC-006)

**Checkpoint**: CI green on lint + type-check, stack-independent.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and repo-level documentation.

- [ ] T040 Run full `quickstart.md` validation (all 6 scenarios) end-to-end and confirm acceptance criteria + contracts are satisfied
- [ ] T041 [P] Update root `README.md` with the two-step boot and the `--profile training` note for the trainer
- [ ] T042 Final `graphify update .` refresh so the committed graph reflects the complete skeleton (Workflow rule: phase ends with a graphify refresh)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup — **blocks all user stories**.
- **User Stories (Phase 3–5)**: All depend on Foundational. US1/US2/US3 are
  mutually independent and can proceed in parallel once Foundational is done.
- **Polish (Phase 6)**: Depends on the desired user stories being complete.

### User Story Dependencies

- **US1 (P1)**: After Foundational. No dependency on US2/US3.
- **US2 (P2)**: After Foundational. Independent (audits files created in Setup/Foundational/US1; T034 sweep also covers US1 files if run after, but US2 is testable on the foundational tree alone).
- **US3 (P3)**: After Foundational. Independent (tooling configs only).

### Within Each Phase

- T011 after T008/T009; T014 after T008–T013; T030 after T027/T029.
- Models/config before services before app factory; orchestration before boot
  verification.

### Parallel Opportunities

- Setup: T002–T006 all [P].
- Foundational: T008–T010, T012, T013, T015–T026 are largely [P] (distinct files);
  serialize only T007→(deps), T011, T014.
- Cross-story: once Foundational completes, US1, US2, and US3 can be staffed in
  parallel.

---

## Parallel Example: Foundational service skeletons

```bash
# After T007 (backend deps) lands, create service skeletons in parallel:
Task: "Create backend/app/core/config.py (Settings, extra='forbid')"      # T008
Task: "Create backend/app/core/logging.py (structlog)"                    # T009
Task: "Create backend/app/core/exceptions.py (exception hierarchy)"       # T010
Task: "Create modelserver/app.py (/healthz no-model)"                     # T020
Task: "Create trainer/train.py + Dockerfile (profile training)"           # T022
Task: "Create frontend/package.json + tsconfig + vite.config.ts"          # T024
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories).
3. Complete Phase 3: User Story 1.
4. **STOP and VALIDATE**: fresh clone → `.env` → `docker compose up` → all default
   services healthy, trainer absent, modelserver "no model loaded". Demo the empty
   running stack.

### Incremental Delivery

1. Setup + Foundational → skeleton exists.
2. US1 → stack boots (MVP).
3. US2 → map navigable via graphify.
4. US3 → CI green.
5. Polish → quickstart validation + README + graph refresh.

---

## Notes

- [P] = different files, no dependencies. [Story] maps task to user story.
- Header comment on every created file is a global convention (FR-002), not just a
  US2 task; T034 is the completeness audit.
- No torch in `modelserver` (Article III); `trainer` only builds under `--profile
  training` (FR-003).
- CI runs lint + type-check only this phase and must never depend on the running
  stack (Article V).
- Commit after each task or logical group; end the phase with `graphify update .`.
