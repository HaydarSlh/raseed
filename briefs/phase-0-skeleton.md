# Phase 0 — Repository skeleton & project map

## Intent
Create the complete agreed folder tree with every file stubbed and carrying a
header comment stating its single responsibility; the whole stack boots empty
from a fresh clone.

## In scope (deliverables)
- Full tree: `backend/app/{core,api,services,repositories,domain,infra,workers}`,
  `backend/{alembic,prompts,tests/{unit,golden,redteam}}`, `modelserver/`,
  `trainer/`, `training/{notebooks}`, `frontend/src/{pages,components,api}`,
  `rag-corpus/`, `scripts/`, `specs/`, `docs/`, `.claude/`, `.github/workflows/`.
- Every stub file begins with a header comment (docstring for .py) answering
  "what is this file for" — these comments are the project map graphify extracts.
- `docker-compose.yml` with all services: postgres(+pgvector), redis, minio,
  vault, migrate (runs Alembic then exits), backend, modelserver, worker,
  frontend, trainer (under compose profile `training`).
- `.env.example`, `.gitignore` (+ Git LFS init), `.graphifyignore`
  (node_modules/, graphify-out/, training/data/, venvs, dist/).
- CI skeleton (lint + type-check) green; `eval_thresholds.yaml` with placeholder
  thresholds at repo root.
- Graphify installed project-scoped; first graph generated.

## Out of scope
Any business logic, auth, models, or real endpoints. Strict refuse-to-boot
guards (they activate in later phases with the artifacts they guard).

## Acceptance criteria
- Fresh clone -> `cp .env.example .env` -> `docker compose up` -> every default
  service healthy. The model-server stub serves `/healthz` reporting
  "no model loaded" WITHOUT crashing (strict hash guard arrives in Phase 2).
- Every file's header comment states its responsibility.
- `/graphify query "where does ingestion live"` returns the correct path.
- CI green on lint + type-check.

## Notes for /plan
Fixed stack per CLAUDE.md. The trainer service must NOT build on default
`docker compose up` (profile `training`). Compose services talk by service name,
never localhost. Named volumes for postgres, minio, redis.
