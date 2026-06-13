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

<!-- Later phases: categorizer threshold, forecaster MAE baseline, retrain trigger
     (100 corrections OR 14 days), drift signals, etc. -->
