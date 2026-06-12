# Data Model: Repository Skeleton & Project Map

Phase 0 introduces **no application/database schema** (Alembic baseline is empty by
design — Article II, no user data yet). The "entities" here are the structural
units of the skeleton itself, captured so tasks and validation have a precise
target.

## Entity: Service

A named unit in the orchestration definition.

| Field | Description | Validation / Rule |
|-------|-------------|-------------------|
| name | Service identifier on the compose network | Unique; addressed by name, never localhost (FR-004) |
| role | infra / migration / app / serving / worker / training | One of the fixed-stack roles |
| profile | Compose profile gating startup | `trainer` → `training`; all others default (FR-003) |
| healthcheck | Readiness probe | Required for every default service (R2); trainer exempt (not on default boot) |
| volume | Named persistent volume | Required for postgres, minio, redis (FR-005); none persist raw user files (Article II) |
| depends_on | Start ordering | Condition-based: infra `service_healthy`, migrate `service_completed_successfully` |

**Instances (default profile)**: postgres, redis, minio, vault, migrate, backend,
modelserver, worker, frontend.
**Instances (training profile)**: trainer.

**Lifecycle**: `migrate` is one-shot (runs Alembic baseline, exits 0). All other
default services are long-running and must reach `healthy`. `trainer` only exists
when the `training` profile is requested and never sits on a request path.

## Entity: Stub File

A placeholder source/config file forming the project map.

| Field | Description | Validation / Rule |
|-------|-------------|-------------------|
| path | Location in the agreed tree | Must fall under an approved top-level area (FR-001) |
| header_comment | One-line single-responsibility statement | Required on 100% of stub files (FR-002, SC-002); docstring for `.py` |
| body | Import-clean placeholder | No business logic, auth, models, or endpoints (FR-012) |

**Rule**: A stub must import cleanly (so lint/type-check pass — SC-006) and contain
no inline prompt strings (Article IV — prompts live in `prompts/`).

## Entity: Layer (backend)

Encodes the constitution's downward-only architecture.

| Layer | Directory | May import from | Must NOT import from |
|-------|-----------|-----------------|----------------------|
| api | `backend/app/api` | services, domain | repositories, infra (directly) |
| services | `backend/app/services` | repositories, domain, infra | api |
| repositories | `backend/app/repositories` | domain | api, services |
| domain | `backend/app/domain` | (pure models) | api, services, repositories, infra |
| infra | `backend/app/infra` | domain | api, services |
| workers | `backend/app/workers` | services, domain, infra | api |

**Rule (Article I)**: imports flow downward only; routers never touch the database.
Phase 0 establishes the directories and header stubs without introducing any
upward import.

## Entity: Configuration (Settings)

| Field | Description | Validation / Rule |
|-------|-------------|-------------------|
| source | Single pydantic-settings class | `extra='forbid'` (Article I) |
| required values | Fail-fast at startup if missing | Startup raises, not silent default (Article I) |
| secret source | Vault (dev mode this phase) | env-file = documented trim rung, not silent (R5, Article V) |

## Entity: Evaluation Thresholds File

| Field | Description | Validation / Rule |
|-------|-------------|-------------------|
| location | `eval_thresholds.yaml` at repo root | FR-009 |
| content | Placeholder thresholds for the 8 CI gates | Syntactically valid; later phases populate (R7) |

## Non-entities (explicitly out of scope this phase)

User, Transaction, Account, Label, Model Registry, Goal, Memory Vector — all
deferred to Phase 1+. No table, migration, or RLS policy is created in Phase 0
beyond the empty Alembic baseline.
