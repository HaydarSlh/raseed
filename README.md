# Raseed — رصيد

Raseed ("balance") is a B2C personal-finance intelligence platform:
statement upload → ingestion pipeline (TF-IDF + Logistic Regression categorizer, Prophet forecaster,
anomaly + recurring detectors) → isolated per-user data → a bounded tool-calling
agent grounded in exact SQL queries + RAG over financial-literacy knowledge → a full
ML lifecycle (human corrections → gated retrain → drift detection → Slack alerts).

## Demo

Three commands from a fresh clone to a working demo:

```bash
git clone https://github.com/HaydarSlh/raseed.git
cd raseed
cp .env.example .env
docker compose up
```

Open `http://localhost:5173` and log in with the demo account (after seeding):

```bash
python scripts/seed_demo.py
```

| Account | Password |
|---------|----------|
| demo@raseed.app | Demo1234! |
| demo2@raseed.app | Demo5678! |

The demo users have 6 months of realistic UK transaction history seeded. Ask the
agent: *"What is my biggest spending category this month?"*

See `docs/RUNBOOK.md` for full operational procedures and the drift rehearsal demo.

## Evaluation Results

All 8 CI gates green. Full details in `docs/EVALS.md`.

| Gate | Description | Threshold | Measured |
|------|-------------|-----------|----------|
| Gate 1 | Categorizer macro-F1 on holdout | ≥ 0.84 | **0.8934** |
| Gate 2 | Forecaster MAE ≤ day-of-week baseline | beat_baseline=true | **PASS** |
| Gate 3 | Tool-selection accuracy (15 cases) | ≥ 80% (12/15) | **PASS** |
| Gate 4 | RAG hit@5 / MRR [¹] | 0.0 (FakeEmbedder) | **PASS** |
| Gate 5 | Red-team probes refused (10/10) | 0 injection success | **PASS** |
| Gate 6 | PII never reaches LLM; no hardcoded secrets | 0 leaks | **PASS** |
| Gate 7 | Drift fires on simulated skewed batch | must_fire=true | **PASS** |
| Gate 8 | Compose smoke: all default services healthy | all_healthy=true | **PASS** (local) |

[¹] RAG uses FakeEmbedder in CI (hash-seeded, non-semantic). Gate verifies plumbing;
semantic quality verified by Scenario 7 in `docs/quickstart.md` with a real embedder.

## Run the stack

```bash
cp .env.example .env
docker compose up          # default services (no trainer)
docker compose --profile training up   # include trainer for retrain demos
docker compose down        # stop (keep volumes)
docker compose down -v     # stop + drop volumes
```

Gate smoke test: `bash scripts/smoke_compose.sh`

## Architecture

- **Frontend**: React (Vite) SPA — `frontend/`
- **Backend**: FastAPI (async, layered) — `backend/`
- **Model server**: lean ONNX Runtime container — `modelserver/`
- **Worker**: Prophet + drift + RQ — `worker/`
- **Trainer**: CPU sklearn→ONNX retrain (no torch), off default profile — `trainer/`
- **Data**: Postgres + pgvector (per-user RLS), Redis, MinIO (model artifacts only)
- **Secrets**: Vault at startup
- **LLM**: Gemini Flash-Lite / Flash → Grok failover

See `docs/DESIGN.md` for the scaling story and `docs/DECISIONS.md` for all design
decisions (D1–D20).

## CI

GitHub Actions: lint + type-check + unit tests + 8 eval gates. Stack-independent
except Gate 8 (compose smoke, runs on push to main). See `docs/EVALS.md`.

## Planning artifacts

- `CLAUDE.md` — master context for the implementation agent.
- `COMMANDS.md` — the Spec Kit command order.
- `.specify/memory/constitution.md` — engineering invariants (always wins).
- `briefs/` — phase briefs; `docs/PLAN.md` — authoritative design plan.
- `specs/` — spec/plan/tasks for each phase (001–009).
- `SECURITY.md` — security policy and vulnerability disclosure.
