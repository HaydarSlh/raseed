# Data Model: Auth, Tenancy & the Infra Spine

All tables except `model_registry` are **user-owned**: they carry `user_id` and are
protected by RLS (`ENABLE` + `FORCE ROW LEVEL SECURITY`) with a policy
`USING (user_id = current_setting('app.user_id')::uuid)` and a matching `WITH CHECK`
on writes. `model_registry` is global (no per-user policy). Created in Alembic
revision `0002_auth_tenancy`. The `vector` extension is **not** enabled this phase —
the `memory` embedding column is deferred to Phase 4 (see Memory below — M1).

## Roles

| Role | Privilege | Used by | Rule |
|------|-----------|---------|------|
| `raseed_app` | non-owner, non-superuser, **NOT** BYPASSRLS | backend, worker (normal jobs) | RLS policies bind; sets `app.user_id` per request |
| `raseed_stats` | **BYPASSRLS** | Phase 3 stats job ONLY | the sole cross-user reader (FR-007); never used by request paths |

## Entity: User

| Field | Type | Rule |
|-------|------|------|
| id | UUID (PK) | fastapi-users id; the value bound to `app.user_id` |
| email | citext, unique | login identifier; duplicate registration rejected |
| hashed_password | text | never logged or returned |
| is_active / is_verified / is_superuser | bool | fastapi-users defaults |
| is_operator | bool, default false | ops access flag — NOT a role hierarchy (DESIGN A) |
| created_at | timestamptz | |

Not RLS-restricted to self for auth flows (the auth layer manages access), but no
endpoint exposes other users' records.

## Entity: Transaction *(structure only this phase)*

| Field | Type | Rule |
|-------|------|------|
| id | UUID (PK) | |
| user_id | UUID (FK→users) NOT NULL | RLS key |
| provenance | enum `rule\|model\|llm\|human` NOT NULL | label source (Art. III) |
| confidence | float NULL | classifier confidence |
| needs_review | bool, default false | flags low-confidence / quarantined labels |
| amount, currency, merchant, occurred_at, category | (minimal cols) | filled/used by Phase 3 ingestion |
| created_at | timestamptz | |

## Entity: Goal · Correction · Memory · Audit Log *(structure only)*

- **Goal**: `id`, `user_id` (RLS), name, target_amount, target_date, created_at.
- **Correction**: `id`, `user_id` (RLS), transaction_id (FK), old_category,
  new_category, confirmed_by_human bool, created_at. The future source of
  human-confirmed training labels (Art. III) — only human-confirmed rows ever train.
- **Memory**: `id`, `user_id` (RLS), `content`, `created_at` (+ audit linkage).
  User-filtered at query time; written only via the future `write_memory` tool.
  **The `embedding vector(N)` column is deferred to Phase 4** (M1): the embedder and
  its dimension are chosen in DESIGN F, and `write_memory` doesn't exist until then,
  so the column would be unwritable dead schema now. Phase 4 adds it (and enables the
  `vector` extension) in its own migration once the dimension is known.
- **Audit Log**: `id`, `user_id` (RLS), action, detail (jsonb), created_at.

## Entity: Model Registry *(global — NOT user-scoped)*

| Field | Type | Rule |
|-------|------|------|
| id | UUID (PK) | |
| name / version | text | |
| sha256 | text | pinned artifact hash (Phase 2 refuse-to-boot guard) |
| status | enum `challenger\|champion\|archived` | promotion state |
| model_card | jsonb | shipped with the artifact |
| created_at | timestamptz | |

No RLS policy; readable by the app role. Governs serving/promotion in Phases 2/5.

## RLS context lifecycle

1. Request authenticated → current-user dependency yields the verified `User.id`.
2. RLS-scoped session dependency runs `set_config('app.user_id', <id>, false)` on
   the connection.
3. All queries in the request see only rows where `user_id = app.user_id`.
4. On connection release, a pool reset hook runs `RESET app.user_id` so the next
   request on that pooled connection starts with no identity (SC-003).

If `app.user_id` is unset/empty, `current_setting('app.user_id', true)` is NULL and
RLS policies match no rows — a missing context fails closed, never open.

## Validation rules (from requirements)

- Every user table has a NOT NULL `user_id` and an RLS policy (FR-004/005, SC-009).
- Identity comes only from the verified session, never request body (FR-002).
- Repository base mandates a user filter even though RLS is the backstop (FR-005,
  defense in depth).
- `transactions.provenance` constrained to the four-value enum (Art. III).
