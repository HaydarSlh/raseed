# Raseed — رصيد

Raseed ("balance") is a B2C personal-finance intelligence platform. This repository
is built spec-driven, one phase at a time. **Phase 0 (the repository skeleton) is in
place** — the whole stack boots empty from a fresh clone.

## Run the skeleton

Two steps, no manual edits:

```bash
cp .env.example .env
docker compose up
```

Every **default** service comes up healthy: `postgres` (pgvector), `redis`, `minio`,
`vault`, a one-shot `migrate` (applies the Alembic baseline then exits), `backend`
(FastAPI, `/healthz`), `modelserver` (lean ONNX stub — reports "no model loaded"),
`worker`, and `frontend` (Vite SPA).

The heavy **trainer** image is gated behind a compose profile and is **not** built or
run on a default `docker compose up`. To opt in:

```bash
docker compose --profile training up
```

Tear down with `docker compose down` (keep volumes) or `docker compose down -v`
(also drop `pgdata`/`redisdata`/`miniodata`).

### Validation

- `bash scripts/smoke_compose.sh` — boot the default stack and assert all default
  services healthy + trainer excluded.
- CI runs lint + type-check only (and never starts the stack): backend `ruff` +
  `mypy` + boot smoke `pytest`, model-server `ruff` + `mypy`, frontend `tsc` +
  `eslint`.

## Planning artifacts

- `CLAUDE.md` — master context for the implementation agent.
- `COMMANDS.md` — the Spec Kit command order.
- `.specify/memory/constitution.md` — engineering invariants (always wins).
- `briefs/` — phase briefs; `docs/PLAN.md` — authoritative design plan v1.1.
- `specs/001-repo-skeleton/` — this phase's spec, plan, research, contracts, tasks.

One phase = one Spec Kit feature. Never improvise answers to `/speckit.clarify` —
resolve them from `docs/PLAN.md`.
