# Phase 1 Research: Auth, Tenancy & the Infra Spine

Stack is fixed by the constitution and `docs/PLAN.md` (DESIGN A); no open
`NEEDS CLARIFICATION`. This records the Phase-1-specific design decisions.

## R1 — RLS context: session GUC set per request, RESET on connection release

- **Decision**: Use a per-request `SELECT set_config('app.user_id', :uid, false)`
  (session-scoped GUC, the `false` = not transaction-local) executed on the
  connection backing the request's session. On release, **reset** it via a
  SQLAlchemy pool `reset`/`checkin` hook running `RESET app.user_id` (or
  `set_config('app.user_id','',false)`). The RLS-scoped session dependency sets it
  at request start from the verified JWT identity.
- **Rationale**: The brief and DESIGN A explicitly require "reset on connection
  release (pooled connections persist it)". A session GUC persists on a pooled
  connection, so an explicit reset is the correctness guarantee; this is exactly
  what SC-003 tests.
- **Alternatives rejected**: Transaction-local `set_config(..., true)` (auto-resets
  at COMMIT) — cleaner in theory but ties identity to an open transaction and does
  not match the brief's "reset on connection release" model or the pooled-reset
  test; rejected. Per-request new connection (no pool) — rejected on cost.

## R2 — RLS enforcement role vs privileged stats role

- **Decision**: The app connects as a **non-owner, non-superuser** role so RLS
  policies apply (table owners/superusers bypass RLS). Add `FORCE ROW LEVEL
  SECURITY` on each user table so even the owner is subject to policy in case of
  misconfig. Define exactly one **privileged role** (BYPASSRLS) reserved for the
  Phase 3 stats job; it is the only identity that can read across users.
- **Rationale**: Art. II — RLS is the backstop and must actually bind the app role;
  FR-007 requires a single privileged cross-user identity for the stats job and
  none for user sessions. DESIGN D: "user-scoped sessions must not compute
  cross-user aggregates."
- **Alternatives rejected**: Running the app as table owner — rejected (owner
  bypasses RLS, defeating the guarantee). Granting the app BYPASSRLS — rejected for
  the same reason.

## R3 — RLS policy shape

- **Decision**: Each user table gets `ENABLE ROW LEVEL SECURITY` + `FORCE` and a
  policy `USING (user_id = current_setting('app.user_id')::uuid)` plus a matching
  `WITH CHECK` for writes. `model_registry` is **not** user-scoped (global) and has
  no per-user policy.
- **Rationale**: FR-005 (DB-layer isolation that holds even on an unscoped query),
  FR-008 (model_registry is global). `WITH CHECK` prevents inserting/altering rows
  into another user's space.
- **Alternatives rejected**: Application-only filtering — rejected (Art. II demands
  DB-layer backstop); a single policy on a view — rejected as more complex than
  per-table policies.

## R4 — Authentication: fastapi-users JWT (bearer)

- **Decision**: fastapi-users with the SQLAlchemy adapter, `BearerTransport` +
  `JWTStrategy`. Routers: register, login (token), and users/me. `User` extends the
  fastapi-users base with an `is_operator` boolean. Identity for RLS is taken from
  the authenticated user dependency only.
- **Rationale**: Fixed stack (fastapi-users JWT). FR-001/002/003; Art. II (JWT-only
  identity). `is_operator` is a boolean, not RBAC (DESIGN A).
- **Alternatives rejected**: Cookie/session transport — JWT bearer is the fixed
  choice; email verification flow — out of scope (no email service yet), documented
  as an assumption.

## R5 — Vault secrets with refuse-to-boot

- **Decision**: At startup, `infra/vault.py` resolves required secrets (JWT signing
  key, model API keys) from Vault. A required-but-missing secret raises and the app
  **refuses to boot**. The `.env.example` defaults remain the documented local
  fallback (an explicit trim rung), selected by `APP_ENV=local`.
- **Rationale**: Art. V / DESIGN G (Vault day 1, refuse-to-boot); FR-010; SC-004.
  Phase 1 introduces the guarded artifact (secrets), so the secret refuse-to-boot
  activates now (distinct from the model-hash guard in Phase 2).
- **Alternatives rejected**: Reading secrets lazily on first use — rejected
  (fail-fast at startup is the requirement); committing secrets — forbidden.

## R6 — Single LLM adapter (Gemini → Grok) + fake double

- **Decision**: `infra/llm.py` exposes one async `complete()`/`generate()` boundary.
  Two-tier routing (Flash-Lite mechanical / Flash synthesis) and Gemini→Grok
  failover live inside it. Every call wraps a timeout + tenacity retry (exponential
  backoff; **4xx not retried**); failures surface as structured `UpstreamError`. A
  `FakeLLM` implementing the same interface is injected in tests and whenever no key
  is configured.
- **Rationale**: Art. V (timeout/retry, 4xx no-retry, Gemini→Grok in one adapter),
  Art. IV (single boundary; prompts from files), FR-013/014, SC-007. The fake keeps
  tests off live models.
- **Alternatives rejected**: Calling provider SDKs from services directly — rejected
  ("no SDK calls anywhere else" per the brief / Art. IV single boundary).

## R7 — Request IDs, logging, tracing, retry helper

- **Decision**: A middleware assigns/propagates a request id into a `contextvar`,
  bound onto structlog via `merge_contextvars` so every log line carries it; the
  worker binds the same field on job entry. An `observability.py` provides a
  `span()` context manager (token/cost fields added when LLM calls exist) and a
  `with_retry()` helper wrapping tenacity for external calls.
- **Rationale**: Art. V (structlog JSON + request IDs across API and worker; span
  per external call; tenacity everywhere external); FR-011; SC-006.
- **Alternatives rejected**: Per-module ad-hoc logging — rejected (consistency and
  correlation required).

## R8 — Data model & migration

- **Decision**: One Alembic revision `0002_auth_tenancy` creates: `users`
  (fastapi-users schema + `is_operator`), `transactions`
  (`provenance` enum, `confidence`, `needs_review`), `goals`, `corrections`,
  `model_registry` (global), `memory` (pgvector embedding + user_id), `audit_log`.
  It enables the `vector` extension, adds RLS policies/roles (R2/R3), and creates
  the app + privileged roles.
- **Rationale**: FR-004/005/008; DESIGN A/B/C structures. One coherent baseline
  keeps the schema reviewable.
- **Alternatives rejected**: Splitting into many micro-migrations — unnecessary for
  a single foundational baseline; deferring RLS to a later migration — rejected
  (isolation must ship with the tables).

## R9 — CI gains a Postgres service for isolation tests

- **Decision**: The CI workflow adds a Postgres (pgvector) service so the
  integration suite (cross-user isolation, unscoped-query block, pooled reset) runs.
  Unit tests (settings fail-fast, adapter failover via fake, exception mapping) stay
  service-free. CI artifacts never come from the running app stack.
- **Rationale**: FR-016/SC-008 require the isolation guarantees proven in CI; RLS
  cannot be tested without a real Postgres. Art. V (CI independent of the running
  *application* stack — a CI service container is not the app stack).
- **Alternatives rejected**: Mocking the DB for RLS tests — rejected (RLS is a
  database behavior; a mock proves nothing). Testing against the compose stack —
  rejected (CI must not depend on the running app stack).
