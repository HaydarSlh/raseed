# Phase 0 Research: Repository Skeleton & Project Map

All technology choices are fixed by the constitution and `docs/PLAN.md`; there are
no open `NEEDS CLARIFICATION` items. This document records the Phase-0-specific
decisions (the *how* of the skeleton) with rationale and rejected alternatives.

## R1 — Orchestration: Docker Compose with a profiled trainer

- **Decision**: One `docker-compose.yml` with services `postgres` (pgvector image),
  `redis`, `minio`, `vault`, `migrate`, `backend`, `modelserver`, `worker`,
  `frontend`, and `trainer`. `trainer` is assigned `profiles: ["training"]` so it
  is excluded from a plain `docker compose up`. `migrate` runs Alembic then exits
  (`restart: "no"`); `backend` depends on `migrate` completing.
- **Rationale**: Brief and PLAN require a single-command empty boot with the heavy
  torch image off the default path (Article III). Compose profiles are the native,
  declarative way to exclude a service from default startup.
- **Alternatives rejected**: A separate `docker-compose.training.yml` overlay —
  rejected because profiles keep one source of truth and match the brief's wording
  (“trainer under compose profile `training`”).

## R2 — Service health and dependency ordering

- **Decision**: Every default service declares a `healthcheck`. Postgres uses
  `pg_isready`; Redis uses `redis-cli ping`; MinIO uses its `/minio/health/live`;
  Vault uses `vault status`; backend, modelserver, and frontend expose a `/healthz`
  (or equivalent) hit by `curl`/wget. `depends_on` uses `condition:
  service_healthy` for infra and `service_completed_successfully` for `migrate`.
- **Rationale**: SC-001/SC-003 require an unattended "all default services healthy"
  outcome; healthchecks + condition-based `depends_on` make that deterministic.
- **Alternatives rejected**: Plain `depends_on` without conditions — rejected
  because it only orders container *start*, not readiness, producing flaky boots.

## R3 — model-server stub: lean, no torch, "no model loaded"

- **Decision**: `modelserver` is a small FastAPI app whose only dependencies are
  `fastapi`, `uvicorn`, `onnxruntime`, `numpy`. `/healthz` returns HTTP 200 with
  `{"status":"ok","model":"none","detail":"no model loaded"}`. No SHA-256 hash
  guard and no refuse-to-boot logic in this phase.
- **Rationale**: Article III forbids torch in serving images and mandates a lean
  model-server; the brief and PLAN explicitly defer the refuse-to-boot guard to
  Phase 2 (FR-010, spec edge case).
- **Alternatives rejected**: Sharing the backend image — rejected because the
  lean/heavy separation must be physical to keep serving images torch-free.

## R4 — Single-responsibility header comments as the project map

- **Decision**: Every stub file begins with a one-line responsibility statement —
  a module docstring for `.py`, a leading `//`/`/* */` comment for TS/JS, a `#`
  comment for YAML/Dockerfiles/config. Content is otherwise an import-clean stub.
- **Rationale**: FR-002 and US2 make these comments the navigable project map that
  Graphify extracts; they must exist on 100% of stub files (SC-002).
- **Alternatives rejected**: A separate `MAP.md` index — rejected because the brief
  requires the map to live *in* the files so Graphify’s AST extraction surfaces it
  and it cannot drift from the code.

## R5 — Configuration: `.env.example` → `.env`, Vault as source of truth

- **Decision**: `.env.example` carries every variable needed to boot the default
  stack with safe local defaults; copying it to `.env` is sufficient (FR-006).
  Vault runs in dev mode this phase and is the declared secret source; the env-file
  path is documented as the first trim-ladder rung, not a silent default.
- **Rationale**: Article V / DESIGN G require Vault day-1 with env-file as an
  explicit documented trim; SC-001 requires a two-step boot with no manual edits.
- **Alternatives rejected**: Committing a working `.env` — rejected (secrets/`sk-`
  leakage risk, Article V); hard-failing without Vault populated — rejected as it
  breaks the two-step boot this phase targets.

## R6 — Backend skeleton honoring downward-only layering

- **Decision**: `backend/app/{core,api,services,repositories,domain,infra,workers}`
  with `core` holding `Settings(extra='forbid')`, structlog config, a lifespan
  context that constructs (stub) singletons, and the domain exception hierarchy.
  `main.py` is an app factory that wires lifespan and boots with no real routes.
- **Rationale**: Article I mandates the layering, single typed settings, lifespan
  singletons, and exception hierarchy; establishing the seams now prevents upward
  imports later.
- **Alternatives rejected**: A flat `app/` package — rejected as it would not encode
  the mandated layer boundaries that later phases depend on.

## R7 — CI: lint + type-check, green and stack-independent

- **Decision**: A GitHub Actions workflow runs `ruff` + `mypy` on the backend and
  `tsc` + `eslint` on the frontend. It installs deps and checks static artifacts
  only — it never starts the compose stack. `eval_thresholds.yaml` sits at repo
  root with placeholder gate thresholds for later phases.
- **Rationale**: FR-008/SC-006 require green lint+type-check independent of the
  running stack; Article V requires CI to never depend on the running stack and
  thresholds committed day-1.
- **Alternatives rejected**: Adding the compose smoke test now — rejected; CI gate 8
  (compose smoke) lands with later phases per PLAN, and Phase 0 only scaffolds it.

## R8 — Versioning, ignores, and Git LFS

- **Decision**: `.gitignore` excludes venvs, `node_modules/`, `dist/`,
  `graphify-out/`, `training/data/`, and secret/`.env` files, and initializes Git
  LFS tracking for model artifacts, fixtures, and the frozen holdout.
  `.graphifyignore` excludes `node_modules/`, `graphify-out/`, `training/data/`,
  venvs, and `dist/`.
- **Rationale**: FR-007 and Article V (CI artifacts via LFS/release assets, never
  the running stack; no committed secrets) and the brief’s explicit ignore lists.
- **Alternatives rejected**: Committing large artifacts directly — rejected (repo
  bloat, Article V mandates LFS/release assets).

## R9 — Pinned image/runtime versions

- **Decision**: Python 3.12, Node 20, PostgreSQL 16 (pgvector), Redis 7, current
  MinIO and Vault images, React 18 + Vite 5. Pins live in Dockerfiles and
  `pyproject.toml`/`package.json`.
- **Rationale**: Reproducible fresh-clone boots (SC-001) require pinned runtimes;
  these are current stable lines compatible with the fixed stack.
- **Alternatives rejected**: Floating `latest` tags — rejected; they break
  reproducibility and Article V’s "decisions backed by a number" discipline.
