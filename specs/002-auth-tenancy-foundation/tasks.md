---
description: "Task list for Phase 1 — Auth, Tenancy & the Infra Spine"
---

# Tasks: Foundation — Auth, Tenancy & the Infra Spine

**Input**: Design documents from `specs/002-auth-tenancy-foundation/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: INCLUDED. The brief's acceptance criteria and FR-016/SC-008 mandate
CI-backed isolation and reset tests, so this phase ships test tasks (RLS isolation,
pooled reset, settings fail-fast, LLM adapter failover). They are written alongside
their implementation; the security tests (US2) must fail before the RLS mechanism
exists and pass after.

**Organization**: Tasks are grouped by user story. Setup + Foundational build shared
infra (engine/session, settings, the schema migration with RLS+roles, request-id
logging, exception handlers); the story phases deliver the three independently
testable outcomes: register/sign-in (US1), DB-enforced isolation (US2), the infra
spine — fail-fast secrets, single model gateway (US3).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1 / US2 / US3 (story-phase tasks only)
- All work extends the existing Phase 0 `backend/` layout; paths are repo-relative.

---

## Phase 1: Setup

**Purpose**: Dependencies and CI/test scaffolding needed by every story.

- [X] T001 Add Phase 1 backend deps to `backend/pyproject.toml`: `fastapi-users[sqlalchemy]`, `hvac` (Vault), `google-genai` (Gemini); confirm `pytest-asyncio` in dev extras. (`pgvector` deferred to Phase 4 with the embedding column — M1.)
- [X] T002 [P] Add a Postgres (pgvector) service + an integration-test job to `.github/workflows/ci.yml` (runs `pytest tests/integration`); keep lint/type-check jobs stack-independent (research R9)
- [X] T003 [P] Create `backend/tests/integration/__init__.py` and `backend/tests/integration/conftest.py` with fixtures: a real async engine/session against the CI Postgres, a helper to set/clear `app.user_id`, and a two-user seed fixture

**Checkpoint**: deps resolve; CI has a Postgres service; integration harness exists.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared spine + schema that all stories depend on. **Blocks US1/US2/US3.**

**⚠️ CRITICAL**: No user story work begins until this phase is complete.

- [X] T004 Create SQLAlchemy declarative `Base` + naming convention in `backend/app/domain/base.py`
- [X] T005 Implement async engine + session factory in `backend/app/infra/db.py` (replace the Phase 0 stub), exposing a session dependency seam
- [X] T006 Extend `Settings` in `backend/app/core/config.py` with JWT signing secret, token lifetime, and required Vault secret keys — keep `extra='forbid'` and fail-fast on missing required values
- [X] T007 Wire `backend/app/core/lifespan.py` to construct engine + session-factory singletons on `app.state` (Vault + LLM adapter singletons added in US3)
- [X] T008 [P] Add request-id middleware + `contextvar` in `backend/app/core/request_context.py` and bind it into structlog in `backend/app/core/logging.py` (request IDs on every log line)
- [X] T009 Register domain-exception handlers (`RaseedError` → structured HTTP) in `backend/main.py` so users never see a stack trace
- [X] T010 [P] Create domain models for all tables in `backend/app/domain/` — `user.py` (+`is_operator`), `transaction.py` (`provenance` enum / `confidence` / `needs_review`), `goal.py`, `correction.py`, `model_registry.py` (global), `memory.py` (`id`, `user_id`, `content`, `created_at`, audit linkage — **NO embedding column**; deferred to Phase 4 — M1), `audit.py` — per data-model.md
- [X] T011 Author Alembic revision `backend/alembic/versions/0002_auth_tenancy.py`: create all tables with NOT NULL `user_id` (except global `model_registry`); the `memory` table has **no embedding/vector column** this phase (deferred to Phase 4 — M1; do NOT enable the `vector` extension here); `ENABLE`+`FORCE ROW LEVEL SECURITY` + `USING/WITH CHECK` policy keyed on `current_setting('app.user_id')::uuid` per user table; create roles `raseed_app` (no BYPASSRLS) and `raseed_stats` (BYPASSRLS) (contracts/rls-tenancy.md)

**Checkpoint**: stack boots with real engine/session; `migrate` applies `0002` with tables, RLS, and roles.

---

## Phase 3: User Story 1 - Register and sign in (Priority: P1) 🎯 MVP

**Goal**: A person can register, sign in (JWT), and reach a protected endpoint;
identity comes only from the verified token.

**Independent Test**: Register → login → `GET /users/me` succeeds with the token,
401 without; wrong credentials rejected; duplicate registration rejected
(quickstart Scenario 1).

- [X] T012 [P] [US1] Auth integration test in `backend/tests/integration/test_auth.py` — register, login, `/users/me` with/without token, wrong creds, duplicate email (contracts/auth-api.md)
- [X] T013 [US1] Implement the fastapi-users `UserManager`/identity service in `backend/app/services/user_service.py`
- [X] T014 [US1] Configure the fastapi-users JWT bearer backend and the current-user dependency in `backend/app/api/deps.py` (identity taken only from the verified token — FR-002)
- [X] T015 [US1] Add register/login/users routers in `backend/app/api/auth.py` and include them (plus CORS for the SPA) in `backend/main.py`
- [X] T016 [P] [US1] Add minimal `frontend/src/pages/Register.tsx` and `Login.tsx`, and extend `frontend/src/api/client.ts` with register/login calls + bearer-token handling

**Checkpoint**: end-to-end register/sign-in works from the frontend shell (MVP).

---

## Phase 4: User Story 2 - Database-enforced per-user isolation (Priority: P1)

**Goal**: A user reads/writes only their own rows — enforced by the database even
when a query omits the user filter — and the per-request identity resets between
pooled requests.

**Independent Test**: Seed two users; under A's context an unscoped repo read
returns zero of B's rows; a write into B's space is rejected; the next pooled
request starts with no `app.user_id` (quickstart Scenarios 2–3).

- [X] T017 [P] [US2] RLS isolation integration test in `backend/tests/integration/test_rls_isolation.py` — own-rows-only, **deliberately unscoped** query returns zero foreign rows, write blocked by `WITH CHECK` (SC-002)
- [X] T018 [P] [US2] RLS reset integration test in `backend/tests/integration/test_rls_reset.py` — `app.user_id` does not carry across reused pooled connections; unset context matches no rows (SC-003)
- [X] T019 [US2] Implement the RLS-scoped session dependency in a new `backend/app/db/session.py` module (with `backend/app/db/__init__.py`), plus the pool reset hook in `backend/app/infra/db.py`: `set_config('app.user_id', <current user>, false)` at request start, `RESET app.user_id` on connection release (research R1). Kept OUT of `app/api/deps.py` so the persistence concern is separate from auth and does not collide with T014 (M2).
- [X] T020 [US2] Implement the user-scoped repository base in `backend/app/repositories/base.py` enforcing a mandatory `user_id` filter (defense in depth behind RLS)
- [X] T021 [P] [US2] Add a schema/role assertion test in `backend/tests/integration/test_rls_roles.py` — every user table has RLS enabled + `user_id`; `raseed_app` lacks BYPASSRLS; `raseed_stats` has it (FR-004/007, SC-009)

**Checkpoint**: cross-user isolation, write-isolation, and pooled reset all pass in CI.

---

## Phase 5: User Story 3 - A reliable infrastructure spine (Priority: P2)

**Goal**: Fail-fast config/secrets, structured logs with request IDs, and one
auditable model gateway with retry/failover; no direct hosted-model calls elsewhere.

**Independent Test**: Boot with a required secret missing → fails loudly; with
example defaults → boots; an unknown config key → rejected; a model call flows
through the single adapter with retry/failover; the repo-grep finds no hosted-model
call outside the adapter (quickstart Scenarios 4–6).

- [X] T022 [P] [US3] Unit test in `backend/tests/unit/test_settings.py` — missing required value fails at startup; an unknown/extra key is rejected (`extra='forbid'`) (SC-004/005)
- [X] T023 [US3] Implement Vault secret resolution in `backend/app/infra/vault.py` and call it in `lifespan` — resolve required secrets at startup, **refuse to boot** if any required secret is missing; `.env.example` defaults remain the documented `APP_ENV=local` fallback (research R5)
- [X] T024 [P] [US3] Implement `backend/app/core/observability.py` — a tracing `span()` context manager and a `with_retry()` tenacity helper (timeout, bounded backoff, **4xx not retried**)
- [X] T025 [US3] Implement the single LLM adapter in `backend/app/infra/llm.py` — Gemini Flash-Lite (mechanical) / Flash (synthesis) with Grok failover, wrapped in `with_retry`; structured `UpstreamError` on total failure; prompts loaded from `backend/prompts/`; include a `FakeLLM` double (contracts/llm-adapter.md)
- [X] T026 [P] [US3] Unit test in `backend/tests/unit/test_llm_adapter.py` — Gemini→Grok failover and 4xx-not-retried, driven by the FakeLLM (SC-007)
- [X] T027 [P] [US3] Add a guard test in `backend/tests/unit/test_single_model_gateway.py` — repo grep finds no hosted-model SDK call outside `app/infra/llm.py`; plus an exception-mapping test (domain error → structured HTTP, no stack trace) (SC-007, FR-012)

**Checkpoint**: fail-fast boot, structured request-id logs, and the single gateway all verified.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T028 [P] Record Phase 1 decisions with numbers in `docs/DECISIONS.md` (token lifetime, retry/backoff policy, RLS reset strategy, and "memory.embedding deferred to Phase 4 with the embedder decision" — M1)
- [X] T029 Run the full `quickstart.md` validation (all 6 scenarios) against the live stack and confirm acceptance criteria + contracts are satisfied
- [X] T030 Refresh the knowledge graph: `graphify update .`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no deps — start immediately.
- **Foundational (Phase 2)**: depends on Setup — **blocks all stories**. T011
  (migration) needs T004/T010 (Base + models); T007 needs T005/T006.
- **US1 (P1)**: after Foundational. Needs the `users` table (T011) and engine/session.
- **US2 (P1)**: after Foundational. Needs all tables + RLS + roles (T011) and the
  session seam (T005). Independent of US1 (uses seeded users, not the auth flow).
- **US3 (P2)**: after Foundational. Largely independent (config/secrets/adapter);
  Vault refuse-to-boot (T023) layers onto the lifespan from T007.
- **Polish (Phase 6)**: after the desired stories are complete.

### Within Stories

- Tests (T012, T017, T018, T021, T022, T026, T027) are written with their story; the
  US2 security tests should fail before T019/T020 and pass after.
- Models → migration → repos/services → endpoints.

### Parallel Opportunities

- Setup: T002, T003 [P].
- Foundational: T008, T010 [P]; T004→T005/T010→T011 serialize.
- US1: T012, T016 [P]. US2: T017, T018, T021 [P]. US3: T022, T024, T026, T027 [P].
- Once Foundational is done, US1 / US2 / US3 can proceed in parallel.

---

## Parallel Example: User Story 2 tests

```bash
# After Foundational, write the failing isolation tests together:
Task: "RLS isolation test (unscoped query blocked) tests/integration/test_rls_isolation.py"  # T017
Task: "RLS reset test (pooled connection) tests/integration/test_rls_reset.py"                # T018
Task: "Schema/role assertion test tests/integration/test_rls_roles.py"                        # T021
```

---

## Implementation Strategy

### MVP First (US1 + US2)

1. Setup → Foundational.
2. US1 (register/sign-in) → demo end-to-end auth.
3. US2 (DB isolation) → the headline security guarantee, proven in CI.
4. **STOP and VALIDATE**: a user can sign in and provably cannot read another
   user's data — the foundational MVP.

### Incremental Delivery

1. Setup + Foundational → schema + spine ready.
2. US1 → auth works. 3. US2 → isolation proven. 4. US3 → fail-fast spine + gateway.
5. Polish → DECISIONS + quickstart validation + graph refresh.

---

## Notes

- Identity only from the verified JWT (FR-002); RLS is the backstop AND repo scoping
  stays (FR-005).
- The migration (T011) carries RLS + roles; US2 owns the runtime set/reset context
  and the proof tests.
- All hosted-model calls go through `app/infra/llm.py` (T025); T027 enforces it.
- Commit on the `002-auth-tenancy-foundation` branch (created right before
  implementation); end with `graphify update .`.
