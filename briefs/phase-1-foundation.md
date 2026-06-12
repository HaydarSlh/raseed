# Phase 1 — Foundation: auth, tenancy & the infra spine

## Intent
A user can register and log in, and every database access is isolated per user
at the database layer, with the cross-cutting infrastructure (config, logging,
tracing, errors, secrets, LLM adapter) in place.

## In scope (deliverables)
- fastapi-users (JWT email/password); the verified token sets the RLS context.
- Alembic baseline migration: users, transactions (with `provenance` enum:
  rule|model|llm|human, `confidence`, `needs_review`), goals, corrections,
  model_registry, memory/audit tables — all user tables with `user_id` + RLS
  policies driven by the per-request `set_config('app.user_id', ...)` dependency,
  RESET on connection release.
- Layered scaffolding made real: domain models, repository base with mandatory
  user scoping, service/api wiring pattern, domain exception hierarchy.
- pydantic-settings (`extra='forbid'`); structlog JSON + request IDs; tracing
  spans utility; tenacity retry/timeout helper.
- Vault wiring: secrets resolve at startup; refuse-to-boot on missing secrets.
- LLM adapter in `infra/`: Gemini Flash-Lite / Flash with Grok failover, plus a
  fake-LLM test double for tests.

## Out of scope
Any ML, ingestion, agent, or frontend feature work beyond login screens.

## Acceptance criteria
- Integration test: User A cannot read User B's rows even through a deliberately
  UNSCOPED repository call (RLS catches it). Test runs in CI.
- A second test proves the session variable resets between pooled requests.
- Boot fails loudly with missing secrets; succeeds with `.env.example` defaults.
- Registration/login flow works end-to-end from the frontend shell.

## Notes for /plan
RLS policy per user table + one privileged role used ONLY by the worker's stats
job (Phase 3). The LLM adapter is the single entry point to any hosted model —
no SDK calls anywhere else.
