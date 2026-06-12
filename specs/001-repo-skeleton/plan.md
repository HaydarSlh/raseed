# Implementation Plan: Repository Skeleton & Project Map

**Branch**: `001-repo-skeleton` | **Date**: 2026-06-12 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/001-repo-skeleton/spec.md`

## Summary

Phase 0 creates the complete agreed repository tree with every file stubbed and
carrying a header comment that states its single responsibility, plus the
orchestration, environment, ignore, CI, and evaluation-threshold scaffolding
needed for the whole stack to boot empty from a fresh clone. No business logic,
auth, models, or real endpoints — only the structural foundation and the minimum
wiring each service needs to report healthy. The model-server stub serves a "no
model loaded" health check without any refuse-to-boot guard (that guard arrives in
Phase 2). The deliverable is verified by: fresh clone → copy env → `docker compose
up` → every default service healthy, lint + type-check CI green, and the project
knowledge graph regenerated so a navigation query resolves a responsibility to its
path.

## Technical Context

**Language/Version**: Python 3.12 (backend, model-server, worker, trainer);
TypeScript 5.x on Node 20 (frontend via Vite + React 18).

**Primary Dependencies**: FastAPI + uvicorn, async SQLAlchemy 2.x, pydantic /
pydantic-settings (`extra='forbid'`), fastapi-users (stub only this phase),
Alembic, structlog, httpx, tenacity, RQ; model-server: onnxruntime + numpy +
FastAPI (no torch); trainer: torch + transformers (build only under the `training`
compose profile); frontend: React + Vite. No business dependencies are exercised
this phase — declarations + import-clean stubs only.

**Storage**: PostgreSQL 16 + pgvector (named volume); MinIO (model artifacts only,
named volume); Redis 7 (sessions + RQ, named volume); HashiCorp Vault (dev mode
this phase). No application schema yet — Alembic baseline revision is empty.

**Testing**: pytest (backend `tests/{unit,golden,redteam}`), import/boot smoke
tests; ruff (lint) + mypy (type-check) as the two CI gates that must be green;
frontend: tsc type-check + eslint. A compose smoke check is scaffolded (full gate
8 lands later).

**Target Platform**: Linux containers orchestrated by Docker Compose on a single
host; services communicate by service name on the compose network.

**Project Type**: Web application (React frontend + FastAPI backend) plus auxiliary
ML/infra services (model-server, worker, trainer) — a multi-service monorepo.

**Performance Goals**: None functional this phase. Operational target only: a fresh
`docker compose up` reaches all default services healthy unattended; the heavy
trainer image is excluded from default startup.

**Constraints**: No business logic, auth, data models, or real endpoints (spec
out-of-scope). No torch in any serving image. No strict refuse-to-boot guards yet.
Services address each other by name, never localhost. Named volumes for postgres,
minio, redis. Secrets via Vault (env-file fallback documented, not silent). Every
stub file opens with a single-responsibility header comment.

**Scale/Scope**: One repository, ~12 top-level areas, ~10 compose services, dozens
of stub files. Single developer/operator audience; no end-user load this phase.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The constitution's articles are evaluated for what Phase 0 must **establish
structurally** versus what later phases **activate**. Phase 0 may not violate any
article; it lays the layout that makes each enforceable.

| Principle | Phase-0 obligation | Status |
|-----------|--------------------|--------|
| I. Layered, Async Architecture | Create `api/services/repositories/domain/infra/workers` dirs with header stubs; single pydantic-settings `Settings(extra='forbid')` stub; lifespan + DI seams present; exception-hierarchy stub. No upward imports introduced. | PASS (establish) |
| II. Isolation & Data Protection | No user data exists yet; RLS/JWT/parser scrub are Phase 1+. Phase 0 must NOT persist raw files, must scope MinIO to artifacts, and must keep webhook stubs ops-only. MinIO bucket is artifacts-only by layout. | PASS (no user data; no violation) |
| III. ML Lifecycle Integrity | model-server stub = onnxruntime+numpy, **no torch**; trainer = single heavy image under `training` profile, off default boot and off any request path; health stub reports "no model loaded" with **no** hash guard yet. | PASS (lean serving enforced now) |
| IV. Bounded Agent & Grounded RAG | `prompts/` directory exists for version-controlled prompts; agent/RAG/tool dirs stubbed; no inline prompt strings introduced. | PASS (establish) |
| V. Quality & Operations | structlog config stub; `eval_thresholds.yaml` at repo root (placeholders); CI lint+type-check green and **independent of the running stack**; Vault is the secret source (env-file documented); `.gitignore` blocks `sk-`-style leakage paths. | PASS (establish) |

**Stack fidelity**: The fixed stack (React/Vite, FastAPI async layered, Postgres+
pgvector RLS, fastapi-users, Redis, MinIO artifacts-only, Vault, lean model-server,
profiled trainer, light worker, Gemini→Grok adapter, Alembic, structlog, GitHub
Actions, Graphify) is reproduced exactly — no substitutions.

**Result**: PASS. No violations; Complexity Tracking left empty. Re-checked
post-design below.

### Post-Design Re-Check

After Phase 1 design (data-model, contracts, quickstart): the layout introduces no
upward imports, no torch in serving images, no persisted user data, no inline
prompts, and keeps CI stack-independent. **Constitution Check still PASS.** No
entries required in Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/001-repo-skeleton/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output — decisions & rationale
├── data-model.md        # Phase 1 output — skeleton "entities" (services, stubs)
├── quickstart.md        # Phase 1 output — boot & validation guide
├── contracts/           # Phase 1 output — service health & compose contracts
│   ├── compose-services.md
│   └── modelserver-healthz.md
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── core/            # settings (pydantic-settings extra='forbid'), logging, lifespan, exceptions
│   ├── api/             # HTTP routers only — stubs (no real endpoints yet)
│   ├── services/        # business logic seams — stubs
│   ├── repositories/    # SQL-only data access — stubs
│   ├── domain/          # Pydantic domain models — stubs
│   ├── infra/           # external adapters (db engine, redis, minio, vault, llm, modelserver client) — stubs
│   └── workers/         # RQ worker entrypoints (stats, drift, slack webhook) — stubs
├── alembic/             # migration env + empty baseline revision
│   └── versions/
├── prompts/             # version-controlled prompt files (placeholder)
├── tests/
│   ├── unit/
│   ├── golden/
│   └── redteam/
├── main.py              # FastAPI app factory + lifespan wiring (boots empty)
├── pyproject.toml       # backend deps, ruff, mypy config
└── Dockerfile

modelserver/             # lean onnxruntime+numpy FastAPI stub; /healthz -> "no model loaded"
├── app.py
├── pyproject.toml
└── Dockerfile

trainer/                 # heavy torch image; built ONLY under compose profile `training`
├── train.py             # entrypoint stub
├── pyproject.toml
└── Dockerfile

training/
└── notebooks/           # Colab foundation-training notebooks (placeholder)

frontend/
├── src/
│   ├── pages/
│   ├── components/
│   └── api/             # typed client seam to backend
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
└── Dockerfile

rag-corpus/              # shared financial-literacy corpus (placeholder, .gitkeep)
scripts/                 # operational scripts (placeholder)
specs/                   # Spec Kit features (this dir)
docs/                    # PLAN.md (exists) + DECISIONS.md, DESIGN.md placeholders
.claude/                 # agent config (exists)
.github/workflows/       # CI: lint + type-check (green on empty skeleton)

docker-compose.yml       # postgres(+pgvector), redis, minio, vault, migrate, backend,
                         #   modelserver, worker, frontend, trainer(profile: training)
.env.example             # copy -> .env is sufficient to boot the default stack
.gitignore               # + Git LFS init (holdout/fixtures/model artifacts tracked via LFS)
.graphifyignore          # node_modules/, graphify-out/, training/data/, venvs, dist/
eval_thresholds.yaml     # repo-root placeholder thresholds (CI gates extend later)
```

**Structure Decision**: Multi-service monorepo (web application + ML/infra
services). The backend follows the constitution's mandated downward-only layering
(`api → services → repositories → domain`, with `infra` for adapters and `workers`
for RQ entrypoints). model-server, trainer, and worker are separate top-level
service directories so the lean/heavy split (Article III, no-torch-in-serving) is
physical, not just logical. The trainer is the single heavy image and is bound to
the `training` compose profile so it never builds on a default `docker compose up`.

## Complexity Tracking

> No constitutional violations. Section intentionally empty.
