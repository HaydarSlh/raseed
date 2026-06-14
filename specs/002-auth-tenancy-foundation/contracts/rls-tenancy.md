# Contract: RLS Tenancy (per-user isolation)

The database is the backstop for isolation; the repository layer scopes as defense
in depth. This contract is the security guarantee Phase 1 must prove in CI.

## Policy contract (every user-owned table)

```
ALTER TABLE <t> ENABLE ROW LEVEL SECURITY;
ALTER TABLE <t> FORCE ROW LEVEL SECURITY;
CREATE POLICY <t>_isolation ON <t>
  USING      (user_id = current_setting('app.user_id')::uuid)
  WITH CHECK (user_id = current_setting('app.user_id')::uuid);
```

- The app connects as `raseed_app` (no BYPASSRLS, not table owner) so policies bind.
- `model_registry` is global: no policy.
- `raseed_stats` (BYPASSRLS) is the only cross-user reader; reserved for the Phase 3
  job; never used on a request path.

## Context lifecycle contract

| Step | Action |
|------|--------|
| request start | `set_config('app.user_id', <jwt user id>, false)` on the session connection |
| during request | every query sees only `user_id = app.user_id` rows |
| connection release | pool reset runs `RESET app.user_id` |
| context unset | `current_setting('app.user_id', true)` is NULL → policies match **no** rows (fail closed) |

## Behavioral contract (CI-tested)

1. **Own-rows-only**: under User A's context, any read returns only A's rows.
   *(FR-005, SC-002)*
2. **Unscoped query still safe**: a repository call that deliberately omits the
   `user_id` filter, run under A's context, returns **zero** of B's rows — RLS
   catches it. *(FR-005, SC-002 — the headline test)*
3. **Write isolation**: an attempt to insert/update a row owned by another user is
   rejected by `WITH CHECK`. *(FR-005)*
4. **Pooled reset**: after a request completes, the next request on the same pooled
   connection starts with no identity; no `app.user_id` carries over. *(FR-006,
   SC-003)*
5. **Schema invariant**: every user-data table has NOT NULL `user_id` + RLS enabled.
   *(FR-004, SC-009)*
6. **No cross-user aggregates for users**: `raseed_app` cannot read across users;
   only `raseed_stats` can. *(FR-007)*
