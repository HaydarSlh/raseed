# scripts/

Utility scripts for demo seeding and compose smoke testing.

## seed_demo.py

Seeds two demo users (`demo@raseed.app` / `demo2@raseed.app`) with six months of
realistic UK transaction history. Idempotent — safe to re-run.

```bash
# With the compose stack running:
DATABASE_URL=postgresql+asyncpg://raseed:raseed_local_dev@localhost:5432/raseed \
  python scripts/seed_demo.py
```

Credentials for the demo UI:
- `demo@raseed.app` / `Demo1234!`
- `demo2@raseed.app` / `Demo5678!`

## smoke_compose.sh

CI Gate #8 compose smoke test. Brings up the default profile, waits for all default
services to report healthy, and confirms the trainer is absent on a default up.

```bash
bash scripts/smoke_compose.sh
```

## Drift rehearsal (backend/scripts/simulate_drift.py)

The drift → retrain → promote demo rehearsal uses the script in the backend package:

```bash
# With the compose stack running and demo data seeded:
docker compose exec worker python /app/scripts/simulate_drift.py
```

See `docs/RUNBOOK.md §Alert response` for the full rehearsal procedure.
