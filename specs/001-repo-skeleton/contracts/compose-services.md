# Contract: Compose Services (Phase 0 boot)

The orchestration definition is the primary interface this phase exposes. This
contract fixes the observable behavior validated by the acceptance criteria.

## Default-profile services (must be healthy after `docker compose up`)

| Service | Role | Healthcheck (intent) | Named volume |
|---------|------|----------------------|--------------|
| postgres | Postgres 16 + pgvector | `pg_isready` succeeds | `pgdata` |
| redis | Redis 7 (sessions + RQ) | `redis-cli ping` → PONG | `redisdata` |
| minio | Object store (artifacts only) | `/minio/health/live` 200 | `miniodata` |
| vault | Secrets (dev mode) | `vault status` reachable | none required |
| migrate | Alembic baseline runner | n/a — one-shot | none |
| backend | FastAPI app (boots empty) | `/healthz` 200 | none |
| modelserver | Lean onnxruntime stub | `/healthz` 200, "no model loaded" | none |
| worker | RQ light worker | process-alive / ping | none |
| frontend | React (Vite) | served index reachable | none |

## Training-profile service (excluded from default boot)

| Service | Profile | Rule |
|---------|---------|------|
| trainer | `training` | Heavy torch image. MUST NOT build or run on a plain `docker compose up`. Never on a request path. |

## Behavioral contract

1. **Two-step boot**: `cp .env.example .env` then `docker compose up` brings every
   default-profile service to `healthy` with no manual edits. *(SC-001, SC-003)*
2. **Ordering**: `migrate` runs after infra is healthy and exits 0; `backend`
   starts only after `migrate` completes successfully.
3. **Trainer exclusion**: `docker compose up` starts zero training-profile
   services; `docker compose --profile training up` is required to build/run
   `trainer`. *(SC-003)*
4. **Addressing**: every service references peers by service name on the compose
   network; no `localhost`/loopback inter-service addressing. *(FR-004)*
5. **Persistence**: postgres, redis, minio use named volumes; no service persists
   raw user statement files anywhere. *(FR-005, Article II)*
6. **Missing env**: starting without a `.env` fails with a clear, actionable
   message rather than a cryptic/silent failure. *(Edge case)*
