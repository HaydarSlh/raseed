# Research: Evals, Demo & Release

All decisions below were resolved from the existing codebase, prior-phase DECISIONS.md
entries, and the clarifications provided before planning.

---

## R1 — Gate 1: Categorizer CI gate implementation

**Decision**: `backend/tests/test_categorizer_gate.py` loads
`training/data/holdout.parquet`, constructs the input text as
`{Transaction Description} [{Transaction Type}]` (matching Phase 2 preprocessing),
runs batch ONNX inference using `onnxruntime.InferenceSession` on
`modelserver/artifacts/categorizer.onnx`, computes macro-F1 with
`sklearn.metrics.f1_score(average='macro')`, and asserts the result ≥
`eval_thresholds.yaml:categorizer.macro_f1_min` (0.84).

**Rationale**: Stack-independent (constitution Art. V). The ONNX artifact is already
committed (Phase 2, SHA-256 = `3f5dc0e0edb4efd017fc515785f2daf2976314738ff14ef733f121c25f45b331`).
ONNX Runtime is already a dev dependency. No model-server HTTP call needed.

**Alternatives considered**: Running inference via `GET /categorize` on the model-server
container. Rejected: requires Docker stack running in CI, violates Art. V.

---

## R2 — Gate 8: Compose smoke test in CI

**Decision**: `docs/smoke_compose.sh` (already committed) is the execution vehicle.
A thin pytest wrapper `backend/tests/test_compose_smoke.py` with
`@pytest.mark.integration` shells out to it. CI runs `pytest -m integration` in a
separate step after the standard suite. If Docker is unavailable the step is skipped
and documented in EVALS.md as "not verified in this CI run."

**Rationale**: Keeps the main pytest suite stack-independent. The `[integration]`
marker is a standard pytest convention for tests requiring external services.

**Alternatives considered**: A separate Makefile target without pytest. Rejected:
inconsistent with using pytest as the single gate runner.

---

## R3 — seed_demo.py: direct AsyncSession vs API calls

**Decision**: `scripts/seed_demo.py` uses `asyncio.run()` + SQLAlchemy AsyncSession.
Users are inserted with argon2 hashed passwords (via `passlib.context`). Transactions
are generated with random UK-realistic data: Sainsbury's, Tesco, Amazon, TfL, etc.;
amounts in GBP; categories drawn from the Phase 2 taxonomy (18 classes). Dates span
the 6 months before the script's run date. Idempotent via `INSERT … ON CONFLICT
(email) DO NOTHING`.

**Rationale**: Avoids dependency on a running FastAPI server. Direct DB access allows
the script to run as a setup step before `docker compose up` has the backend healthy.

**Alternatives considered**: HTTP API + JWT. Rejected: requires a running server,
valid credentials, and token management in a one-off script.

---

## R4 — simulate_drift.py: no changes needed

`backend/scripts/simulate_drift.py` already exists and is covered by Gate 7
(`test_drift_gate.py`). Phase 7 only documents its usage in RUNBOOK.md.

---

## R5 — RAG thresholds: remain at 0.0

`rag.hit_at_5_min` and `rag.mrr_min` remain 0.0. FakeEmbedder produces hash-seeded
non-semantic vectors; the gate verifies retrieval pipeline wiring, not semantic
quality. Inflating thresholds would misrepresent the gate's actual guarantee.
Semantic quality is verified by the quickstart scenario (real embedder, running stack).

---

## R6 — EVALS.md structure

Table columns: Gate | Description | Threshold Key | Committed Value | Last Measured | Notes.
RAG rows include a footnote: "FakeEmbedder CI — semantic quality not measured here;
see quickstart.md for real-embedder validation."

---

## R7 — DESIGN.md deferred sections

Three sections to complete:
1. **Scaling story** (~1 page): per-user Prophet cost (O(1) per recompute), pgvector
   index scaling, RLS row filtering at scale, horizontal stateless API scaling.
2. **Isolation & erasure**: RLS enforcement, right-to-erasure purge path (Phase 6),
   model-unlearning limitation.
3. **ML lifecycle**: champion/challenger gate, drift detection signals, retrain cadence,
   Slack alerts (Phase 5).

Content is synthesized from `docs/PLAN.md` sections already written in prior phases.

---

## R8 — README submission block

The submission block in `README.md` requires real measured values for all 8 gates.
Values are read from the final CI run before the v0.1.0 tag. The block uses the
format already established in the README placeholder (if present) or a new section
`## Evaluation Results`.
