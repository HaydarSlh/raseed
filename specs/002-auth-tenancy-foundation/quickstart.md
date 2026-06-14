# Quickstart & Validation: Auth, Tenancy & the Infra Spine

Proves Phase 1: a person can register/sign in, data is isolated at the database
layer (even through an unscoped query), the identity context resets between pooled
requests, and the service fails fast on missing secrets. References
[contracts/](./contracts/) and [data-model.md](./data-model.md).

## Prerequisites

- Phase 0 stack boots (`cp .env.example .env` → `docker compose up`).
- `.env` carries the local defaults (JWT secret, model keys blank — FakeLLM used).
- Migrations applied by the `migrate` service (revision `0002_auth_tenancy`).

## Scenario 1 — Register and sign in *(US1)*

```bash
# register
curl -fsS -X POST http://localhost:8000/auth/register \
  -H 'content-type: application/json' \
  -d '{"email":"a@example.com","password":"correct-horse-battery"}'
# login -> bearer token
curl -fsS -X POST http://localhost:8000/auth/jwt/login \
  -H 'content-type: application/x-www-form-urlencoded' \
  -d 'username=a@example.com&password=correct-horse-battery'
# authenticated request
curl -fsS http://localhost:8000/users/me -H "Authorization: Bearer <token>"
```

**Expected**: register 2xx; login returns a token; `/users/me` 2xx with the token,
401 without it; wrong password → rejected, no token. *(SC-001)*

## Scenario 2 — Cross-user isolation, including an unscoped query *(US2, headline)*

Run the integration test (real Postgres required):

```bash
cd backend && pytest tests/integration/test_rls_isolation.py -q
```

**Expected**: with two seeded users, under User A's context every read returns only
A's rows; a deliberately **unscoped** repository call returns **zero** of User B's
rows (RLS catches it); a write into B's space is rejected by `WITH CHECK`.
*(SC-002; contracts/rls-tenancy.md)*

## Scenario 3 — Pooled-connection reset *(US2)*

```bash
cd backend && pytest tests/integration/test_rls_reset.py -q
```

**Expected**: after a request completes, the next request on the same pooled
connection starts with `app.user_id` unset — no identity carries over (fails closed,
matches no rows until set). *(SC-003)*

## Scenario 4 — Fail-fast secrets & strict config *(US3)*

```bash
# missing required secret -> refuse to boot
APP_ENV=production VAULT_TOKEN= docker compose up backend   # expect startup failure
# unknown config key -> rejected
echo "BOGUS_KEY=1" >> .env && docker compose up backend     # expect startup failure
```

**Expected**: missing required secret → loud startup failure, no traffic served;
unknown config key → startup rejected; example-defaults (`APP_ENV=local`) → boots.
*(SC-004, SC-005)*

## Scenario 5 — Structured logs with request IDs *(US3)*

```bash
curl -fsS http://localhost:8000/users/me -H "Authorization: Bearer <token>"
docker compose logs backend | tail -5
```

**Expected**: log lines are JSON and carry a per-request identifier; the same field
appears on worker job logs. *(SC-006)*

## Scenario 6 — Single model gateway *(US3)*

```bash
cd backend
pytest tests/unit/test_llm_adapter.py -q       # failover + 4xx-no-retry via FakeLLM
grep -rEn "google\.generativeai|genai|x\.ai|grok" app --include=*.py | grep -v "app/infra/llm.py"
```

**Expected**: adapter tests pass against the FakeLLM (Gemini→Grok failover, 4xx not
retried); the grep finds **no** hosted-model call outside `app/infra/llm.py`.
*(SC-007; contracts/llm-adapter.md)*

## CI

The CI workflow adds a Postgres (pgvector) service so Scenarios 2–3 run as gates;
unit suites (Scenarios 4, 6) need no service. Lint + type-check stay green. CI never
depends on the running application stack.

## Done When

- All six scenarios pass; acceptance criteria in [spec.md](./spec.md) and the three
  contracts are satisfied; `graphify update .` refreshed.
