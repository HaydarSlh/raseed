# Feature Specification: Categorizer — Trained Offline, Served Lean

**Feature Branch**: `003-categorizer-model`

**Created**: 2026-06-14

**Status**: Draft

**Input**: User description: "briefs/phase-2-categorizer.md — A transaction description goes in; a category + calibrated confidence comes out, from a model fine-tuned by the developer, behind a lean in-stack service."

## Clarifications

### Session 2026-06-14

- Q: How should the spec handle the gate macro-F1 bar and operating threshold, which can't be known until training runs? → A: Ratcheting floor + beat-baseline — the always-binding gate is "beats the classical baseline by a recorded margin"; the absolute macro-F1 floor is seeded from the first champion's measured holdout score (minus a small tolerance) and may only ratchet upward, never down. Both numbers live in `eval_thresholds.yaml` with rationale.
- Q: Is the ≥97% precision operating threshold applied as one global cut or per-category? → A: Per-class thresholds — a confidence threshold per category so each holds ≥97% precision where data allows; categories with too few validation samples default to always-route-for-review. The configuration stores a category→threshold map.
- Q: How granular should the locked taxonomy be for v1? → A: Coarse — consolidate the source dataset into ~10–15 broad categories (favoring samples-per-class, per-class F1, and a meaningful per-class threshold).

### Session 2026-06-15 (post-analyze remediation)

- Q: FR-016 said the artifact "MUST be sourced from the artifact store," contradicting the plan's mounted-LFS approach with MinIO deferred to Phase 5. Which is authoritative? → A: The plan; the spec was out of date. FR-016 amended — the foundation artifact is mounted + content-pinned this phase, artifact-store-sourced loading deferred to the retraining phase, and the serving component loads behind a thin "get current artifact" seam so the swap is non-breaking.
- Q: What is "too few validation samples" for the always-review sentinel (FR-009)? → A: Fewer than **20** validation samples for a category → `always_review`.
- Q: SC-001 is a p95 target — what measures it? → A: The quickstart validation owns the p95 measurement of record (a small latency benchmark over representative inputs vs the 200 ms target); the gate's `max_inference_latency_ms` is a distinct single-call bound.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Categorize a transaction via the served model (Priority: P1)

A consumer of the platform (initially the developer validating the service, later
the ingestion pipeline) sends a single transaction description — for example
`"STARBUCKS STORE #1234 SEATTLE WA"` — to the categorizer service and receives a
single best category from the locked taxonomy, a calibrated confidence score, and
a short ranked list of alternative categories. The service is reachable over HTTP
inside the application stack and answers quickly enough to sit on the ingestion
path without becoming a bottleneck.

**Why this priority**: This is the headline deliverable of the phase — the whole
point is that a description goes in and a category + confidence comes out from a
real, served model. Without it nothing downstream (the ingestion pipeline, the
agent) has a categorizer to call. It is the minimum that delivers value.

**Independent Test**: With the champion artifact in place, start the service and
POST a set of representative descriptions; confirm each response carries a category
drawn only from the locked taxonomy, a confidence in [0,1], and ranked
alternatives, and that a health check reports the service ready. No training,
ingestion, or other phase is required.

**Acceptance Scenarios**:

1. **Given** the service is running with a valid loaded model, **When** a caller
   submits a transaction description, **Then** the response contains exactly one
   primary category from the locked taxonomy, a calibrated confidence value, and a
   ranked list of top-k alternative categories with their scores.
2. **Given** the service is running, **When** a caller submits a description whose
   top score is below the operating threshold for its predicted category, **Then**
   the response still returns the best category and confidence but is marked as
   low-confidence so the consumer can route it for review.
3. **Given** the service is running, **When** a health check is requested, **Then**
   it reports ready only while a verified model is loaded.
4. **Given** a malformed or empty description, **When** it is submitted, **Then**
   the service returns a structured validation error, not a stack trace.

---

### User Story 2 - Prove the model is good enough before it ships (Priority: P1)

A maintainer opens a pull request that changes the categorizer (a new artifact, a
new threshold, or training code). Continuous integration evaluates the candidate
model against a frozen holdout set that nothing else is allowed to touch, and the
change is allowed to merge only if the model clears a committed quality bar and
beats the simple classical baseline. The holdout and the artifact reach CI from
version control / release storage, never from a running service.

**Why this priority**: This is the trust guarantee for the phase. A served model
that has not been proven on a clean, never-trained-on holdout is not shippable. The
gate is what lets every later phase build on the categorizer without re-checking
it, and it protects against silent regressions.

**Independent Test**: In CI, with no application stack running, run the gate
against the committed holdout and candidate artifact; confirm it passes when the
model clears the bar and beats the baseline, and fails (blocking merge) when a
deliberately degraded model is supplied.

**Acceptance Scenarios**:

1. **Given** a candidate model and the frozen holdout available from version
   control / release storage, **When** the gate runs in CI, **Then** it computes
   macro-F1 on the holdout and passes only if the candidate beats the classical
   baseline by at least the committed margin AND meets or exceeds the committed
   absolute macro-F1 floor.
2. **Given** a candidate model below the absolute floor OR not beating the baseline
   by the committed margin, **When** the gate runs, **Then** it fails and blocks the
   merge.
3. **Given** a maintainer attempts to lower the absolute macro-F1 floor to admit a
   weaker model, **When** that change is reviewed, **Then** it is rejected — the
   floor only ratchets upward.
4. **Given** the gate is running, **When** it needs the model or holdout, **Then**
   it obtains them from committed artifacts (version control / release asset) and
   at no point calls a running service.

---

### User Story 3 - Reproducible training and honest model provenance (Priority: P2)

The developer prepares the dataset, locks the category taxonomy, and produces a
deterministic train/validation/test split with a frozen holdout. They train three
approaches offline — a classical baseline, a fine-tuned language model, and a
zero-shot large-language-model baseline — and record one comparison table
(macro-F1, per-class F1, latency, cost per call). The winning model is exported to
the lean serving format and ships with a model card stating the data hash, the
metrics, the freeze policy, and the pinned content hash of the artifact. Anyone can
re-run the preparation and reproduce the same split and the same recorded numbers.

**Why this priority**: Reproducibility and provenance are what make the served
model (US1) and the gate (US2) trustworthy and auditable, and they set up the
retraining lifecycle in a later phase. They are essential but sit behind the two
P1 outcomes because they are the means by which those outcomes are produced and
defended rather than the runtime behavior itself.

**Independent Test**: Re-run dataset preparation with the fixed seeds and confirm
the split (including the holdout) is identical; confirm the comparison table exists
with concrete numbers for all three approaches; confirm the model card lists the
data hash, metrics, freeze policy, and a content hash that matches the shipped
artifact.

**Acceptance Scenarios**:

1. **Given** the raw source dataset, **When** preparation is run with the fixed
   seeds, **Then** it produces the same stratified train/validation/test split and
   the same frozen holdout every time.
2. **Given** the three trained approaches, **When** the comparison is recorded,
   **Then** the decision log contains macro-F1, per-class F1, latency, and cost per
   call for all three, plus the explicit rule used to pick the winner and the
   explicit rule used to choose the operating threshold.
3. **Given** the winning model, **When** it is exported and packaged, **Then** a
   model card accompanies it recording the data hash, the metrics, the freeze
   policy (full fine-tune for the foundation model; partial unfreeze for in-stack
   retrains in a later phase), and a pinned content hash that exactly matches the
   served artifact.

---

### Edge Cases

- **Missing or corrupt artifact at startup**: the serving component must refuse to
  start rather than serve from an unknown or partial model.
- **Artifact content hash does not match the pinned value**: the serving component
  must refuse to start (no silent fallback to a "close enough" model).
- **Description in an unexpected language or full of noise/symbols**: the service
  still returns its best category and a (likely low) confidence; it never errors on
  legitimate-but-odd text.
- **Empty, whitespace-only, or oversized description**: rejected with a structured
  validation error.
- **A category present in the source data but excluded from the locked taxonomy**:
  preparation maps or drops it deterministically; the served model never emits a
  category outside the locked taxonomy.
- **Severe class imbalance**: evaluation reports per-class F1 (not only macro-F1)
  so a rare category collapsing is visible and can fail the gate.
- **Rare category with too few validation samples to set a threshold**: its
  per-category operating threshold defaults to "always route for review" rather
  than guessing a cut that can't be validated to 97% precision.
- **Tie or near-tie between top categories**: alternatives are returned ranked so
  the ambiguity is visible to the consumer.
- **The frozen holdout is accidentally referenced during training/threshold
  selection**: this must be prevented — the holdout is touched only by the gate.

## Requirements *(mandatory)*

### Functional Requirements

#### Taxonomy & dataset

- **FR-001**: The system MUST define a single locked (closed-set) category taxonomy
  that is version-controlled; every prediction the service returns MUST be a member
  of this taxonomy. The taxonomy MUST be coarse — approximately 10–15 broad
  categories — consolidated from the source dataset via a version-controlled
  consolidation map (favoring samples-per-class and per-class F1).
- **FR-002**: Dataset preparation MUST derive its examples from the designated
  source banking-transactions dataset and produce a stratified
  train/validation/test split using fixed seeds, such that the split is byte-for-
  byte reproducible on re-run.
- **FR-003**: A frozen holdout set MUST be carved out during preparation, committed
  to version control via large-file storage, and used ONLY by the quality gate —
  never during training, model selection, or threshold selection.

#### Offline training & comparison

- **FR-004**: Training MUST be performed offline (developer-run, on GPU) and MUST
  NOT require any training framework to be present in any serving image.
- **FR-005**: Three approaches MUST be evaluated — a classical baseline, a
  fine-tuned language model, and a zero-shot large-language-model baseline — each
  measured on macro-F1, per-class F1, latency, and cost per call.
- **FR-006**: The three-way comparison numbers MUST be recorded in the project
  decision log, along with the explicit rule used to select the winning model.
- **FR-007**: The winning model MUST be the one that ships; the selection rule and
  its outcome MUST be auditable from the decision log.

#### Operating threshold & calibration

- **FR-008**: The served confidence MUST be calibrated so that a precision-based
  threshold rule is meaningful.
- **FR-009**: Operating thresholds MUST be chosen **per category** by an explicit,
  committed rule (the default rule: for each category, the highest confidence
  threshold that still holds at or above 97% precision on the validation set) and
  stored as a category→threshold map in the committed evaluation-threshold
  configuration. Categories with **fewer than 20 validation samples** — too few to
  estimate precision meaningfully — MUST default to "always route for review" (i.e.,
  never auto-accepted).
- **FR-010**: For a prediction whose top score falls below the operating threshold
  for its predicted category, the service MUST flag the result as low-confidence so
  consumers can route it for human review (the service still returns its best
  category).

#### Lean serving

- **FR-011**: The system MUST provide a lean model-serving component exposing a
  prediction operation that returns, for a transaction description, the best
  category, a calibrated confidence, and a ranked list of top-k alternative
  categories with scores.
- **FR-012**: The serving component MUST expose a health/readiness check that
  reports ready only while a verified model is loaded.
- **FR-013**: The serving component MUST refuse to boot when its model artifact is
  missing OR when the artifact's content hash does not match the pinned value
  (strict refuse-to-boot is active in this phase).
- **FR-014**: The serving component MUST remain lean — it MUST carry only inference
  dependencies and MUST NOT include heavy training frameworks.
- **FR-015**: The serving component MUST be reachable over HTTP from within the
  application stack.
- **FR-016**: The served model artifact MUST be pinned by content hash. For this
  phase the immutable foundation artifact is delivered as a **mounted, content-
  pinned artifact** committed via large-file storage; **artifact-store-sourced
  loading (and hot reload) is deferred to the later retraining phase**, when runtime
  artifact rotation first exists. The artifact store remains reserved for model
  artifacts only. To make that future swap non-breaking, the serving component MUST
  load its artifact behind a thin "**get current artifact**" seam, so the source can
  change (mounted file → store-by-hash) without altering boot or hash-verification
  logic.
- **FR-017**: The service MUST return structured errors (never a stack trace) for
  invalid input or internal failure.

#### Model card & provenance

- **FR-018**: The exported model MUST ship with a model card recording the data
  hash, the evaluation metrics, the freeze policy, and the pinned content hash of
  the artifact.
- **FR-019**: The freeze policy in the model card MUST state: full fine-tune for
  the foundation model; partial unfreeze for in-stack retrains in a later phase.

#### Quality gate (CI)

- **FR-020**: A CI quality gate MUST evaluate the candidate model on the frozen
  holdout and pass only if BOTH conditions hold: (a) the candidate's macro-F1
  exceeds the classical baseline's macro-F1 by at least the committed margin
  (always binding), AND (b) the candidate's macro-F1 meets or exceeds the committed
  absolute macro-F1 floor. A result failing either condition MUST block merge.
- **FR-020a**: The absolute macro-F1 floor MUST be seeded from the first champion's
  measured holdout macro-F1 (minus a small committed tolerance) and MUST only ever
  ratchet upward over time — it MUST NOT be lowered to admit a weaker model.
- **FR-021**: The gate MUST obtain the model and holdout from committed artifacts
  (large-file storage or release asset) and MUST NOT depend on any running service.
- **FR-022**: The committed gate values — the beat-baseline margin and the absolute
  macro-F1 floor — MUST live in the shared evaluation-threshold configuration,
  alongside the per-category operating-threshold map, so every bar is explicit and
  version-controlled with its rationale.

### Key Entities *(include if feature involves data)*

- **Category Taxonomy**: the locked, closed set of categories the model may emit;
  the contract every prediction conforms to.
- **Transaction Description**: the free-text input (e.g., a statement memo line)
  the categorizer maps to a category.
- **Prediction**: the output — primary category, calibrated confidence, ranked
  top-k alternatives, and a low-confidence flag relative to the predicted
  category's operating threshold.
- **Model Artifact**: the exported, served model, identified and pinned by a
  content hash; this phase delivers it as a mounted, large-file-storage-committed
  artifact loaded through the "get current artifact" seam (artifact-store-sourced
  loading deferred to the retraining phase).
- **Model Card**: the provenance record accompanying the artifact — data hash,
  metrics, freeze policy, pinned content hash.
- **Frozen Holdout Set**: the never-trained-on evaluation set, committed via
  large-file storage, consumed only by the gate.
- **Operating Threshold Configuration**: the committed evaluation thresholds — the
  gate's beat-baseline margin and ratcheting absolute macro-F1 floor, plus the
  per-category operating-threshold map — and the rules that produced them.
- **Evaluation Comparison**: the recorded three-way table (classical / fine-tuned /
  zero-shot) of macro-F1, per-class F1, latency, and cost per call.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For any transaction description, the served categorizer returns a
  primary category from the locked taxonomy, a calibrated confidence, and ranked
  alternatives, with a 95th-percentile response time under 200 ms per prediction.
- **SC-002**: On the frozen holdout, the shipped model achieves macro-F1 at or
  above the committed absolute floor AND exceeds the classical baseline's macro-F1
  by at least the committed margin; the floor is never lowered across releases.
- **SC-003**: At the committed per-category operating thresholds, every category
  with sufficient validation data holds at least 97% precision on validation among
  its auto-accepted predictions, so only genuinely uncertain ones are routed for
  review.
- **SC-004**: The serving component refuses to start 100% of the time when its
  artifact is missing or its content hash does not match the pinned value.
- **SC-005**: The quality gate runs entirely from committed artifacts with zero
  dependency on a running service, and a model below the bar blocks merge in 100% of
  attempts.
- **SC-006**: The decision log records concrete numbers for all three approaches
  (macro-F1, per-class F1, latency, cost per call), plus the winner-selection rule
  and the operating-threshold rule.
- **SC-007**: The serving component carries only inference dependencies (no
  training frameworks), verifiable by inspecting the shipped component.
- **SC-008**: Every shipped artifact has a model card whose pinned content hash
  exactly matches the served artifact, and which records the data hash, metrics,
  and freeze policy.
- **SC-009**: Re-running dataset preparation with the fixed seeds reproduces an
  identical split and identical frozen holdout.

## Assumptions

- **Source dataset**: the source is `laramee26openBankTransactionData.xlsx` (UK/GBP
  open banking transactions); its native categories are cleaned and consolidated into
  an 18-category locked taxonomy during preparation, with the consolidation map
  version-controlled. (The original plan named the Kaggle USA set; it was synthetic and
  was replaced on 2026-06-16 — see `docs/DECISIONS.md`.)
- **Operating-threshold rule default**: thresholds are **per category**; the
  committed rule is, for each category, "the highest confidence threshold holding
  ≥ 97% precision on validation," matching the brief's example. The resulting
  category→threshold map is stored in the evaluation-threshold configuration;
  categories lacking enough validation samples default to always-route-for-review.
- **Gate value defaults**: the gate has two committed values — a beat-baseline
  margin (always binding) and an absolute macro-F1 floor. The floor is seeded from
  the first champion's measured holdout macro-F1 minus a small committed tolerance,
  and thereafter only ratchets upward; both values and their rationale are recorded
  in the evaluation-threshold configuration.
- **Winning approach**: the fine-tuned language model is expected to win, but the
  recorded comparison decides; whichever wins under the recorded rule ships.
- **Threshold application boundary**: the service returns calibrated scores plus a
  low-confidence flag computed against the predicted category's committed operating
  threshold; downstream consumers
  (the ingestion pipeline, a later phase) own how a low-confidence result is
  handled (e.g., marking a transaction as needing review).
- **Single-item prediction is the contract for this phase**; batch prediction, if
  any, is an additive convenience and not required for acceptance.
- **Offline training environment** (developer GPU notebook) is available to the
  developer; the platform stack does not perform foundation training.
- **Stack orchestration** from the foundation phase is in place and reused; this
  phase adds the serving component and the artifact, not new infrastructure
  primitives. The served artifact is mounted and content-pinned this phase; the
  artifact store (reserved for model artifacts only) is wired as the serving source
  in the later retraining phase via the "get current artifact" seam.
- **Source dataset provenance**: the raw dataset is **not committed** (size /
  licensing). It is provided by the developer — dropped manually into a git-ignored
  `training/data/raw/` (currently `laramee26openBankTransactionData.xlsx`) — and the
  preparation scripts read it from that path. Everything not data-dependent
  (the model-server against fixtures, the gate mechanism against stand-ins, and all
  training/export code) is buildable before the data lands.

## Out of Scope

- The ingestion pipeline (in-memory parsing, PAN/IBAN scrubbing, the rules/weak-
  supervision layer, persistence of categorized transactions) — a later phase.
- Automated retraining, champion/challenger promotion at runtime, drift detection,
  and operator promotion flows — a later phase.
- Per-user personalization of categories, multi-language localization, and
  hyperparameter search depth beyond what selecting the winner requires.

## Dependencies

- The locked category taxonomy and the consolidation map from the source dataset.
- Large-file storage (or release assets) for the frozen holdout and the model
  artifact, reachable by CI.
- The foundation phase's artifact store and stack orchestration.
