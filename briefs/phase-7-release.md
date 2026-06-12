# Phase 7 — Evals, demo & release

## Intent
Everything is provable: all gates real-numbered and green, the demo rehearsed,
docs complete, release tagged.

## In scope (deliverables)
- All eight CI gates green with committed thresholds in eval_thresholds.yaml:
  (1) categorizer F1, (2) forecaster MAE vs baseline, (3) tool-selection golden
  set, (4) RAG golden set, (5) red-team, (6) redaction, (7) drift-fire,
  (8) compose smoke test from fresh clone.
- `scripts/seed_demo.py`: demo users with months of realistic history (enough
  for Prophet seasonality and the lifecycle demo).
- Drift -> retrain -> promote demo rehearsed end-to-end with simulate_drift.py.
- Docs finalized: DESIGN.md (incl. the one-page scaling story), DECISIONS.md
  (every decision backed by its number), EVALS.md, SECURITY.md, RUNBOOK.md,
  README mapping the system.
- Final graphify refresh; tag `v0.1.0`.

## Acceptance criteria
- Fresh clone -> `cp .env.example .env` -> `docker compose up` -> working demo.
- CI fully green end-to-end; submission block in README filled with real numbers.

## Notes for /plan
No new features in this phase. Anything discovered missing becomes either a
fix (if a gate depends on it) or a documented future-work line.
