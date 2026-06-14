# Implementation Plan: Foundation — Auth, Tenancy & the Infra Spine

**Branch**: `002-auth-tenancy-foundation` | **Date**: 2026-06-14 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/002-auth-tenancy-foundation/spec.md`

## Summary

Phase 1 turns the empty skeleton into a foundation with real identity and tenancy.
A person can register and sign in via fastapi-users (JWT email/password); the
verified token drives a per-request Postgres RLS context (`app.user_id`) set on the
connection and **reset on release**, with repository-layer user scoping as defense
in depth. An Alembic baseline creates the user-owned tables (users, transactions
with `provenance`/`confidence`/`needs_review`, goals, corrections, model_registry,
memory vectors, audit log) with RLS policies, plus one privileged role reserved for
the later stats job. The cross-cutting spine becomes real: typed settings
(`extra='forbid'`), Vault secret resolution with refuse-to-boot on missing secrets,
structlog JSON + request IDs, a tracing-span utility, a tenacity timeout/retry
helper, the domain-exception→HTTP mapping, and the single LLM adapter (Gemini
Flash-Lite/Flash → Grok failover) with a fake double for tests. Verified by CI
integration tests proving cross-user isolation (even through an unscoped query) and
session-variable reset between pooled requests.

## Technical Context

**Language/Version**: Python 3.12 (backend); TypeScript 5 / React 18 (frontend
register/sign-in screens only).

**Primary Dependencies**: fastapi-users[sqlalchemy] (JWT, bearer transport), async
SQLAlchemy 2.x + asyncpg, Alembic, pydantic-settings, structlog, httpx, tenacity,
hvac (Vault client), google-genai (Gemini) with an HTTP path to Grok via the
adapter. psycopg2-binary remains for the sync Alembic runner. (pgvector and the
`memory` embedding column are deferred to Phase 4 with the embedder decision — M1.)

**Storage**: PostgreSQL 16. New user-owned tables with `user_id` and per-table RLS
policies keyed on `current_setting('app.user_id')`. The pgvector extension / memory
embedding column are deferred to Phase 4 (M1). Vault (dev mode) holds the JWT
signing secret and model API keys. Redis present (sessions/RQ) but session state
minimal this phase.

**Testing**: pytest + pytest-asyncio. Integration tests against a real Postgres
(RLS cannot be tested without it): cross-user isolation through an unscoped repo
call, and session-var reset across pooled connections. A fake-LLM double keeps
tests off any live model. CI gains a Postgres service; lint+type-check stay green.

**Target Platform**: Linux containers via the existing docker-compose stack;
services addressed by name.

**Project Type**: Web application (FastAPI backend + React frontend) — extends the
Phase 0 monorepo layout; no new top-level structure.

**Performance Goals**: None functional. The RLS context set/reset adds one
statement per request boundary — acceptable; correctness over latency this phase.

**Constraints**: Identity only from the verified JWT (never request body). RLS is
the backstop AND repo scoping is kept. Connection-release reset is mandatory (no
identity bleed). Secrets from Vault; refuse-to-boot on missing required secret.
Every hosted-model call goes through the single adapter. No ML/ingestion/agent work.

**Scale/Scope**: Per-user isolation model; ~7 new tables; auth + infra spine;
minimal frontend auth screens. No load targets.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

This phase **activates** the invariants Phase 0 only established structurally.

| Principle | Phase-1 obligation | Status |
|-----------|--------------------|--------|
| I. Layered, Async Architecture | Real `domain` models, `repositories` (SQL only, mandatory user scoping), `services` (auth/identity), `api` routers (fastapi-users); async throughout; DI for session + identity; `Settings(extra='forbid')` extended; exception→HTTP handlers wired in `main`. | PASS (activate) |
| II. Isolation & Data Protection (NON-NEGOTIABLE) | `user_id` on every user table; RLS policies on each; per-request `set_config('app.user_id', …)` from verified JWT, **reset on connection release**; repo scoping as depth; identity never from body; one privileged cross-user role reserved for the stats job. No raw files / MinIO user data (N/A this phase). | PASS (activate) — CI-tested |
| III. ML Lifecycle Integrity | `transactions.provenance` (`rule\|model\|llm\|human`), `confidence`, `needs_review`, `corrections`, and `model_registry` **structures** created. No serving/training change; no torch added. | PASS (structure only) |
| IV. Bounded Agent & Grounded RAG | No agent/RAG this phase. `prompts/` stays file-based; the LLM adapter introduces no inline prompts. | PASS (no scope) |
| V. Quality & Operations | tenacity timeout/retry in the adapter (4xx not retried), Gemini→Grok failover inside the single adapter; structlog JSON + request IDs across API + worker; tracing-span utility; Vault secrets, refuse-to-boot on missing; `grep -r "sk-"` clean; isolation tests in CI; a decision number recorded in DECISIONS.md. | PASS (activate) |

**Stack fidelity**: fastapi-users JWT, Postgres+pgvector RLS via `app.user_id`,
Vault, Gemini→Grok adapter, Alembic, structlog — exactly the fixed stack, no
substitutions.

**Result**: PASS. No violations; Complexity Tracking empty. Re-checked post-design.

### Post-Design Re-Check

After Phase 1 design (data-model, contracts, quickstart): the design keeps
downward-only layering, routes identity solely from the JWT, enforces RLS + repo
scoping + connection-reset, channels all model calls through one adapter, and adds
no torch and no inline prompts. **Constitution Check still PASS.** Complexity
Tracking remains empty.

## Project Structure

### Documentation (this feature)

```text
specs/002-auth-tenancy-foundation/
├── plan.md              # This file
├── research.md          # Phase 0 output — RLS reset strategy, fastapi-users, adapter
├── data-model.md        # Phase 1 output — tables, columns, RLS policies, roles
├── quickstart.md        # Phase 1 output — boot + isolation/reset validation
├── contracts/           # Phase 1 output
│   ├── auth-api.md           # register / login / me endpoints + session contract
│   ├── rls-tenancy.md        # RLS policy + set/reset context contract
│   └── llm-adapter.md        # single model-gateway contract (failover, retry, fake)
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root — extends Phase 0)

```text
backend/
├── app/
│   ├── core/
│   │   ├── config.py        # extend Settings: jwt secret, token lifetime, vault keys
│   │   ├── logging.py       # add request-id binding
│   │   ├── exceptions.py    # (exists) — handlers registered in main
│   │   ├── lifespan.py      # build engine, session factory, Vault load, adapter, fake-LLM toggle
│   │   ├── observability.py # NEW: tracing-span utility + tenacity timeout/retry helper
│   │   └── request_context.py # NEW: request-id middleware + contextvar
│   ├── api/
│   │   ├── auth.py          # NEW: fastapi-users routers (register, login, users)
│   │   └── deps.py          # NEW: auth / current-user dep ONLY (M2)
│   ├── db/
│   │   └── session.py       # NEW: RLS-scoped session dependency (set/reset app.user_id) (M2)
│   ├── services/
│   │   └── user_service.py  # NEW: UserManager / identity service
│   ├── repositories/
│   │   └── base.py          # NEW: user-scoped repository base (mandatory user filter)
│   ├── domain/
│   │   ├── user.py          # NEW: User (+ is_operator)
│   │   ├── transaction.py   # NEW: provenance/confidence/needs_review
│   │   ├── goal.py · correction.py · model_registry.py · memory.py (no embedding — M1) · audit.py  # NEW
│   ├── infra/
│   │   ├── db.py            # engine + session factory + pool reset hook for app.user_id
│   │   ├── vault.py         # resolve secrets at startup; refuse-to-boot on missing
│   │   └── llm.py           # single adapter: Gemini Flash-Lite/Flash -> Grok; FakeLLM
│   └── workers/             # (unchanged stubs; privileged stats role defined in migration)
├── alembic/versions/
│   └── 0002_auth_tenancy.py # tables + RLS policies + app/privileged roles
└── tests/
    ├── unit/                # settings fail-fast, adapter failover (fake), exception mapping
    └── integration/         # NEW: cross-user RLS, unscoped-query block, pooled-reset

frontend/src/
├── pages/{Register.tsx,Login.tsx}   # NEW minimal auth screens
└── api/client.ts                    # extend: auth calls + token handling
```

**Structure Decision**: Extend the Phase 0 monorepo in place. New code lands in the
existing layered packages (no new top-level dirs), honoring downward-only imports.
A new `backend/tests/integration/` is added because RLS guarantees require a real
Postgres and cannot be unit-tested in isolation; CI gains a Postgres service for
that suite.

## Complexity Tracking

> No constitutional violations. Section intentionally empty.
