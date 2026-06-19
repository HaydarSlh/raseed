# Feature Specification: Evals, Demo & Release

**Feature Branch**: `009-evals-demo-release`

**Created**: 2026-06-17

**Status**: Draft

**Input**: User description: "Phase 7 — Evals, demo & release. All eight CI gates real-numbered and green with committed thresholds in eval_thresholds.yaml..."

## User Scenarios & Testing *(mandatory)*

### User Story 1 — CI Gates All Green (Priority: P1)

An operator or reviewer can clone the repository, run the CI pipeline, and see all
eight quality gates pass with real numeric thresholds committed to source. Each gate
produces a human-readable pass/fail result against an agreed threshold stored in
`eval_thresholds.yaml`.

**Why this priority**: CI gates are the single source of truth for release readiness.
Without them green, no other deliverable can be trusted.

**Independent Test**: Run `pytest` targeting each gate module; all eight gate tests
pass with thresholds read from `eval_thresholds.yaml`.

**Acceptance Scenarios**:

1. **Given** a fresh clone with eval fixtures present, **When** CI runs, **Then** all
   eight gates report PASS with the actual numeric value above (or equal to) the
   committed threshold.
2. **Given** a model whose F1 is below the threshold, **When** Gate 1 runs, **Then**
   it reports FAIL and blocks the pipeline.
3. **Given** an `eval_thresholds.yaml` file, **When** a reviewer opens it, **Then**
   every gate has a named, numeric threshold recorded alongside the most-recent
   measured value.

---

### User Story 2 — Demo Seed & Rehearsal (Priority: P2)

A developer or evaluator can run a single script to populate the system with realistic
demo users and months of transaction history, then rehearse the full drift → retrain
→ promote lifecycle end-to-end.

**Why this priority**: Without seeded data the demo is empty; without rehearsal the
lifecycle story cannot be shown to reviewers.

**Independent Test**: Run `scripts/seed_demo.py`; verify demo users exist with ≥ 6
months of transactions. Run `scripts/simulate_drift.py`; verify it triggers a retrain
and the new model is promoted (or blocked) by the gate.

**Acceptance Scenarios**:

1. **Given** a running stack, **When** `seed_demo.py` is executed, **Then** demo
   users appear with multi-month transaction history sufficient for Prophet
   seasonality detection and the ML lifecycle demo.
2. **Given** seeded data, **When** `simulate_drift.py` is run, **Then** a drift
   alert fires, an RQ retrain job is queued, and the champion/challenger gate either
   promotes or blocks the new model.
3. **Given** no prior data, **When** a fresh seed is requested, **Then** the script
   is idempotent — it can be re-run without duplicating users.

---

### User Story 3 — Finalized Documentation (Priority: P3)

A new contributor or external reviewer can understand the entire system, every
operational procedure, and every design decision from the committed documentation
without needing to ask anyone.

**Why this priority**: Documentation is the lasting artifact of the project; it must
be complete before the release tag is cut.

**Independent Test**: All five required documents exist (`DESIGN.md`, `DECISIONS.md`,
`EVALS.md`, `SECURITY.md`, `RUNBOOK.md`) and each covers its required scope (verified
by section-heading checks).

**Acceptance Scenarios**:

1. **Given** the repository, **When** a reviewer reads `DESIGN.md`, **Then** it
   contains a one-page architecture overview and a scaling story.
2. **Given** the repository, **When** a reviewer reads `DECISIONS.md`, **Then** every
   design decision is backed by a number and a rationale.
3. **Given** the repository, **When** a reviewer reads `EVALS.md`, **Then** it lists
   all eight gate thresholds alongside their most-recent measured values.
4. **Given** the repository, **When** a reviewer reads `RUNBOOK.md`, **Then** it
   covers service startup, secret rotation, retraining procedure, and incident
   response.

---

### User Story 4 — Fresh-Clone Demo (Priority: P4)

Anyone can go from a fresh clone to a working demo in three commands, with no
manual intervention beyond copying the example `.env` file.

**Why this priority**: The acceptance criterion for the entire project is a
demonstrable, runnable system from a clean checkout.

**Independent Test**: On a machine with no prior state, run
`git clone → cp .env.example .env → docker compose up`. Verify the UI loads and
the agent responds to a financial query.

**Acceptance Scenarios**:

1. **Given** a machine with Docker and no prior raseed state, **When** the three
   commands are run, **Then** all services start without error and the UI is
   accessible.
2. **Given** the running demo, **When** a demo user logs in, **Then** their seeded
   transaction history is visible and the agent answers questions about it.

---

### User Story 5 — Release Tag (Priority: P5)

An operator can identify the exact source code corresponding to the initial public
release via a git tag and an updated README.

**Why this priority**: Tagging is the final gate-keeping step; without it the release
is not formally closed.

**Independent Test**: `git tag v0.1.0` exists on main; `README.md` contains the
submission block filled with real gate numbers; graphify knowledge graph reflects the
final codebase state.

**Acceptance Scenarios**:

1. **Given** all gates green and docs complete, **When** the release is cut, **Then**
   `git tag v0.1.0` points to the merge commit and is pushed to the remote.
2. **Given** the README, **When** a reviewer reads the submission block, **Then** all
   eight gate numbers are filled in with real measured values.

---

### Edge Cases

- What happens if a CI gate threshold is not present in `eval_thresholds.yaml`?
  The gate test must fail with a clear error, not silently pass.
- What happens if `seed_demo.py` is run against a database that already has demo
  users? The script must be idempotent and not create duplicates.
- What happens if `simulate_drift.py` triggers a retrain but the new model score
  equals (not beats) the champion? The gate must block promotion (strict `>`
  comparison).
- What if a required documentation section is missing? The doc-existence gate must
  detect and report missing sections by heading name.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST commit a `eval_thresholds.yaml` file to the repository
  root containing numeric pass thresholds and most-recent measured values for all
  eight CI gates.
- **FR-002**: All eight CI gate tests MUST pass in the GitHub Actions pipeline using
  only committed fixtures (no running stack dependency).
- **FR-003**: Gate 1 MUST validate categorizer macro-F1 against the committed
  threshold.
- **FR-004**: Gate 2 MUST validate forecaster MAE against a naive baseline, with the
  improvement ratio threshold committed.
- **FR-005**: Gate 3 MUST validate tool-selection accuracy against a committed golden
  set.
- **FR-006**: Gate 4 MUST validate RAG retrieval quality against a committed golden
  set.
- **FR-007**: Gate 5 MUST confirm all red-team probes are refused (10/10).
- **FR-008**: Gate 6 MUST confirm no PII pattern reaches the LLM path in redaction
  tests.
- **FR-009**: Gate 7 MUST confirm drift detection fires and triggers the retrain
  queue in a smoke test.
- **FR-010**: Gate 8 MUST be a compose smoke test that starts all services from a
  fresh state and confirms health endpoints respond.
- **FR-011**: `scripts/seed_demo.py` MUST create demo users with ≥ 6 months of
  realistic transaction history covering multiple categories.
- **FR-012**: `scripts/simulate_drift.py` MUST inject synthetic distribution shift
  and confirm the drift-detection worker fires.
- **FR-013**: `DESIGN.md` MUST contain a system architecture overview and a
  one-page scaling story.
- **FR-014**: `DECISIONS.md` MUST list every design decision with a unique number and
  rationale; no decision may lack a number.
- **FR-015**: `EVALS.md` MUST list all eight gate thresholds and measured values in a
  structured table.
- **FR-016**: `RUNBOOK.md` MUST cover: service startup, secret rotation, retraining
  procedure, alert response, and right-to-erasure procedure.
- **FR-017**: `README.md` MUST contain a submission block filled with the real,
  measured gate values from the final CI run.
- **FR-018**: The release MUST be tagged `v0.1.0` on the main branch after all gates
  are green and docs are complete.
- **FR-019**: `SECURITY.md` MUST be verified complete (secret management, PII
  boundary, model-unlearning limitation, disclosure process).
- **FR-020**: The graphify knowledge graph MUST be refreshed after all changes are
  committed (final `graphify update .`).

### Key Entities

- **EvalThreshold**: A named gate with a numeric threshold, a measured value, and a
  pass/fail status. Stored in `eval_thresholds.yaml`.
- **DemoUser**: A synthetic user with seeded transaction history, goals, and memory.
  Created idempotently by `seed_demo.py`.
- **GoldenSet**: A committed fixture file (JSON/YAML) containing input–expected-output
  pairs used by Gates 3 and 4.
- **ReleaseTag**: The `v0.1.0` git tag marking the release commit.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All 8 CI gates report PASS in the GitHub Actions pipeline with
  thresholds committed in `eval_thresholds.yaml`.
- **SC-002**: `seed_demo.py` populates ≥ 2 demo users, each with ≥ 6 months of
  transactions across ≥ 5 spending categories, completing in under 60 seconds.
- **SC-003**: `simulate_drift.py` triggers a drift alert and retrain job in under
  30 seconds on a running stack.
- **SC-004**: Fresh-clone demo (`git clone → cp .env.example .env →
  docker compose up`) reaches a healthy, interactive state in under 5 minutes on a
  machine with Docker pre-installed.
- **SC-005**: All 5 required documentation files exist with all required sections
  present (verified by heading-level check).
- **SC-006**: `DECISIONS.md` contains entries for all design decisions (≥ 15
  numbered decisions from Phases 1–7).
- **SC-007**: The `v0.1.0` release tag exists on the remote main branch.
- **SC-008**: `README.md` submission block contains real gate numbers (not
  placeholders) for all 8 gates.

## Assumptions

- All prior phases (1–6) are merged to main before Phase 7 begins; no Phase 7 task
  introduces new application features.
- CI gate fixtures (model weights, holdout set, golden sets) are already committed via
  Git LFS or release assets from prior phases; Phase 7 only ensures thresholds are
  recorded and the gate tests pass.
- Gate 8 (compose smoke test) may run in a GitHub Actions environment with Docker
  available; if Docker is unavailable in CI, it is marked `[integration]` and
  skipped with a documented note.
- `seed_demo.py` generates synthetic data only; it never contacts external financial
  data providers.
- The `v0.1.0` tag is cut after all gates are green on main; no pre-release tags are
  created.
- `SECURITY.md` from Phase 6 already exists; Phase 7 verifies and extends it as
  needed, not replaces it.
