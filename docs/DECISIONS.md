<!-- DECISIONS.md — every design decision backed by a number (constitution Art. V).
     One row per decision: what, the number that justifies it, and the date. -->

# Raseed Decisions Log

Every design decision is recorded here with the number that backs it. Phases append
rows; nothing is decided "by feel."

| Date | Decision | Number / Rationale | Phase |
|------|----------|--------------------|-------|
| 2026-06-12 | Trainer is the single heavy image, off the default compose profile | 0 serving images contain torch (Art. III) | 0 |
| 2026-06-12 | Pinned runtimes: Python 3.12, Node 20, Postgres 16, Redis 7 | Reproducible fresh-clone boot (SC-001) | 0 |
| 2026-06-12 | CI runs lint + type-check only this phase | Brief/PLAN scope; full 8 gates land per phase | 0 |
| 2026-06-14 | memory.embedding deferred to Phase 4 with the embedder decision | embedder/dimension chosen in Phase 4 (DESIGN F) and `write_memory` doesn't exist until then; the column would be unwritable dead schema now | 1 |
| 2026-06-14 | RLS reset strategy: session-dep finally-block + pool event hook (defense in depth) | R1: session GUC persists on pooled connection; explicit RESET on both connection teardown paths ensures SC-003 (no identity bleed) | 1 |
| 2026-06-14 | JWT signing secret stored in Settings; Vault overrides at startup in non-local envs; APP_ENV=local uses .env default | R5: fail-fast refuse-to-boot on missing Vault secret in production; local trim rung documented in .env.example (Art. V) | 1 |
| 2026-06-14 | Retry policy: max 3 attempts, exponential backoff 1-8s, 30s timeout, 4xx not retried | R6/Art. V: bounded backoff prevents quota exhaustion; 4xx is a client error — retrying wastes budget and won't fix it | 1 |
| 2026-06-14 | deps.py holds auth concern only; RLS-scoped session dep moved to db/session.py | M2: separates auth from persistence concern; eliminates parallel-task conflict between T014 and T019 | 1 |

<!-- Later phases: categorizer threshold, forecaster MAE baseline, retrain trigger
     (100 corrections OR 14 days), drift signals, etc. -->
