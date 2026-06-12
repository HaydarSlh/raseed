# Quickstart & Validation: Repository Skeleton & Project Map

This guide proves Phase 0 is complete: the empty stack boots from a fresh clone,
the project map is navigable, and CI is green. It references
[contracts/](./contracts/) and [data-model.md](./data-model.md) rather than
duplicating them.

## Prerequisites

- Docker + Docker Compose (single host)
- Git with Git LFS installed (`git lfs install`)
- Python 3.12 and Node 20 (only for running CI checks locally; not needed to boot)
- Graphify installed project-scoped (already done in this repo)

## Scenario 1 — Fresh clone boots the whole stack empty *(US1, P1)*

```bash
git clone <repo-url> raseed && cd raseed
cp .env.example .env
docker compose up -d
docker compose ps
```

**Expected**:
- Every default-profile service (postgres, redis, minio, vault, migrate, backend,
  modelserver, worker, frontend) is `healthy` (migrate has exited 0). *(SC-001,
  SC-003)*
- `trainer` is **not** present in `docker compose ps`. *(SC-003)*

Verify the migrate one-shot exited cleanly:

```bash
docker compose ps -a    # migrate shows Exited (0)
```

## Scenario 2 — model-server reports "no model loaded" *(US1, contract)*

```bash
curl -fsS http://localhost:<modelserver_port>/healthz
```

**Expected**: HTTP 200 with body reporting `"no model loaded"`; the container does
not crash or refuse to boot. See
[contracts/modelserver-healthz.md](./contracts/modelserver-healthz.md). *(SC-004)*

## Scenario 3 — Trainer stays off the default boot *(US1, SC-003)*

```bash
docker compose up -d                       # trainer NOT built/started
docker compose --profile training build trainer   # only this opts in
```

**Expected**: the plain `up` neither builds nor runs `trainer`; it appears only
with the `training` profile.

## Scenario 4 — Navigable project map *(US2, P2)*

Open any stub file and confirm its first lines state its single responsibility,
then query the knowledge graph:

```bash
graphify update .
graphify query "where does ingestion live"
```

**Expected**: the query resolves to the correct ingestion path (e.g.,
`backend/app/services/...`). 100% of stub files carry a header comment. *(SC-002,
SC-005)*

## Scenario 5 — CI green on lint + type-check *(US3, P3)*

Locally mirror the CI gates (they do not require the running stack):

```bash
# backend
cd backend && ruff check . && mypy .
# frontend
cd ../frontend && npm run typecheck && npm run lint
```

**Expected**: lint and type-check pass on the empty skeleton. The GitHub Actions
workflow runs the same checks and is green; it never starts the compose stack.
*(SC-006)*

## Scenario 6 — Missing env fails clearly *(edge case)*

```bash
rm -f .env && docker compose up
```

**Expected**: startup fails with a clear, actionable message about the missing
environment file (not a silent or cryptic failure).

## Teardown

```bash
docker compose down            # keep named volumes
docker compose down -v         # also remove pgdata/redisdata/miniodata
```

## Done When

- All six scenarios pass.
- Acceptance criteria in [spec.md](./spec.md) and the contracts in
  [contracts/](./contracts/) are satisfied.
- The knowledge graph is refreshed (`graphify update .`).
