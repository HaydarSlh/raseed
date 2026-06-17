# Implementation Plan: Evals, Demo & Release

**Branch**: `009-evals-demo-release` | **Date**: 2026-06-17 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/009-evals-demo-release/spec.md`

## Summary

Phase 7 proves the system is ready to ship: all eight CI gates produce real numeric
results against committed thresholds in `eval_thresholds.yaml`, two demo users are
seeded with six months of realistic UK transactions, every required documentation
file is complete, and the repository is tagged `v0.1.0`. No new application features
are introduced — anything discovered missing is either fixed (if a gate depends on it)
or recorded as future work.

## Technical Context

**Language/Version**: Python 3.12 (backend, scripts) · Node 20 / TypeScript (frontend)

**Primary Dependencies**: pytest · SQLAlchemy (AsyncSession) · ONNX Runtime ·
python-multipart · asyncpg · structlog · docker compose (Gate 8 CI step)

**Storage**: Postgres 16 (seeded demo data via SQLAlchemy) · Redis 7 (session flush)

**Testing**: pytest (backend) · Vitest (frontend, no new tests this phase)

**Target Platform**: Linux server (CI) + local Docker Compose (dev/demo)

**Project Type**: Release / hardening phase — no new application surface

**Performance Goals**:
- `seed_demo.py` completes in under 60 s on a running stack
- `simulate_drift.py` triggers drift alert in under 30 s
- Fresh `docker compose up` reaches healthy state in under 5 min

**Constraints**:
- No new features; anything missing is a fix or future-work note
- CI gates run stack-independently (committed fixtures) — Gate 8 is the only exception
- RAG thresholds stay at 0.0 with documented FakeEmbedder note (not fake-inflated)
- Model artifact already committed (Phase 2, LFS-tracked); Gate 1 reads it via ONNX Runtime

**Scale/Scope**: 2 demo users, ≥ 6 months of transactions each (~180 rows/user)

## Constitution Check

| Article | Concern | Status |
|---------|---------|--------|
| Art. I (Layered, Async) | seed_demo.py uses AsyncSession directly; no router bypassed | ✅ PASS |
| Art. II (Isolation & Data Protection) | Demo users created with explicit user_id; RLS applies; no PII crosses LLM | ✅ PASS |
| Art. III (ML Lifecycle Integrity) | Gate 1 reads committed ONNX artifact (SHA-256 pinned); holdout never touched by retrain | ✅ PASS |
| Art. IV (Bounded Agent & Grounded RAG) | No agent changes; tool-selection and RAG gates are read-only checks | ✅ PASS |
| Art. V (Quality & Operations) | All gate tests read `eval_thresholds.yaml`; CI never depends on running stack (Gate 8 exempted with `[integration]` marker); every decision backed by DECISIONS.md number | ✅ PASS |

## Research Decisions

**R1 — Gate 1 (categorizer) test strategy**
Decision: Load `training/data/holdout.parquet`, run ONNX inference via the ONNX
Runtime Python API directly (not via the model server HTTP call), compute macro-F1
with scikit-learn, compare against `eval_thresholds.yaml:categorizer.macro_f1_min`.
Rationale: Stack-independent; the ONNX artifact is already committed (Phase 2,
LFS-tracked at `modelserver/artifacts/categorizer.onnx`). ONNX Runtime is already
in the backend dev dependencies. Input text = `{description} [{type_code}]` matching
the training preprocessing.
File: `backend/tests/test_categorizer_gate.py`

**R2 — Gate 8 (compose smoke) test strategy**
Decision: Keep `docs/smoke_compose.sh` as the CI execution vehicle; add a thin pytest
wrapper `backend/tests/test_compose_smoke.py` marked `@pytest.mark.integration` that
shells out to the script. CI runs it in a separate `[integration]` step using
`pytest -m integration`. Without Docker in CI the step is skipped; documented in
`docs/EVALS.md`.
Rationale: Consistent with Art. V — pytest is the gate runner; the shell script
handles Docker orchestration.
File: `backend/tests/test_compose_smoke.py`

**R3 — seed_demo.py approach**
Decision: Script uses SQLAlchemy AsyncSession directly (bypasses HTTP API), wrapped in
`asyncio.run()`. Inserts users with argon2-hashed passwords, then inserts transactions
with randomised UK-realistic merchants, amounts, categories, and dates spanning the
last 6 months from the run date. Idempotent via `ON CONFLICT DO NOTHING` on email.
Users: `demo@raseed.app` and `demo2@raseed.app`.
Rationale: HTTP API requires a valid JWT and a running server; direct insert is
simpler for a seed script and still respects all schema constraints.
File: `scripts/seed_demo.py`

**R4 — simulate_drift.py location**
Decision: `backend/scripts/simulate_drift.py` already exists from Phase 5. Phase 7
documents its usage in `docs/RUNBOOK.md` and adds a top-level `scripts/` symlink
for discoverability. No code changes needed.

**R5 — EVALS.md structure**
Decision: `docs/EVALS.md` — one row per gate:
Gate ID | Description | Threshold Type | Threshold Value | Last Measured | CI Status
The RAG gate rows include a footnote explaining FakeEmbedder limitations.

**R6 — RAG gate thresholds**
Decision: `rag.hit_at_5_min` and `rag.mrr_min` remain at 0.0. A documentation note
in both `eval_thresholds.yaml` and `docs/EVALS.md` explains the FakeEmbedder
limitation. Semantic quality is verified by the quickstart scenario only.
Rationale: Inflating to a fake non-zero value would create a false green signal (constitution
Art. V: decisions backed by numbers, not wishful thinking).

**R7 — DESIGN.md completeness**
Decision: Fill the three deferred sections (Scaling story, Isolation & erasure, ML
lifecycle) with concise summaries derived from docs/PLAN.md and DECISIONS.md.
No new design decisions introduced; this is purely a documentation-completion task.
File: `docs/DESIGN.md`

**R8 — DECISIONS.md Phase 7 entries (D16–D20)**
Gate 1 test strategy (D16), Gate 8 CI exemption (D17), RAG 0.0 threshold rationale
(D18), seed_demo.py direct-DB approach (D19), v0.1.0 tag timing (D20).

## Project Structure

### Documentation (this feature)

```text
specs/009-evals-demo-release/
├── plan.md         ← this file
├── research.md     ← generated (Phase 0)
├── data-model.md   ← generated (Phase 1)
├── quickstart.md   ← generated (Phase 1)
└── tasks.md        ← /speckit-tasks output
```

### Source Code (new / modified files)

```text
# New files
backend/tests/test_categorizer_gate.py   ← Gate 1: categorizer F1 on holdout
backend/tests/test_compose_smoke.py      ← Gate 8: @integration compose smoke wrapper
scripts/seed_demo.py                     ← demo user seeding (direct AsyncSession, idempotent)
docs/EVALS.md                            ← all 8 gate thresholds + measured values
docs/RUNBOOK.md                          ← ops: startup, secrets, retrain, erasure, drift

# Modified files
docs/DESIGN.md                           ← fill three deferred sections
docs/DECISIONS.md                        ← append D16–D20 (Phase 7 decisions)
README.md                                ← fill submission block with real gate values
eval_thresholds.yaml                     ← add Gate 1 measured value annotation + Gate 8 note
.github/workflows/ci.yml                 ← add Gate 1 step + Gate 8 [integration] step
CLAUDE.md                                ← update plan pointer to Phase 7 plan
```

## Complexity Tracking

No constitution violations. Phase 7 has no new architectural surface; it is
documentation + two new gate tests + one seed script.
