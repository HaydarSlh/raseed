# Feature Specification: The ML Lifecycle & Ops

**Feature Branch**: `007-lifecycle-ops`

**Created**: 2026-06-17

**Status**: Draft

**Input**: User description: "briefs/phase-5-lifecycle.md — User corrections flow into a gated, human-approved retraining loop with drift detection — visible on an ops page and alerting to Slack."

## Clarifications

### Session 2026-06-17

- Q: When a drift signal crosses its threshold, which signals automatically enqueue a retrain (vs. only alarm)? → A: Primary only — mean confidence + correction rate enqueue a retrain; PSI + new-merchant rate are alarm/alert-only. (The simulated held-out-merchant batch drops confidence, so CI gate #7 still fires a retrain.)
- Q: How often does the drift monitor evaluate the production model's signals? → A: A once-daily scheduled job on the light worker, plus on-demand invocation (used by the drift simulation and CI gate #7).
- Q: How does the cooldown/idempotency apply across the multiple retrain trigger sources (count, time, manual, drift)? → A: One global cooldown/idempotency window across all sources (at most one retrain per window); the operator's manual button can force-override it.
- Q: Who reviews and confirms quarantined LLM relabels to upgrade them to human-confirmed training data? → A: The owning user, in their own review queue (no user-level transaction data is surfaced to operators).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Review and correct flagged transactions (Priority: P1)

A user opens a review queue showing every transaction the system flagged as
low-confidence (`needs_review`). For each row they confirm the suggested
category or pick a different one. Each human decision becomes a confirmed
correction. The user can also choose, in a personal setting, whether flagged
rows wait for their manual review or are auto-relabeled by an assistant;
auto-relabels visibly update the row but are held in a separate
"awaiting confirmation" list and never count as training data until the user
confirms them.

**Why this priority**: Human-confirmed corrections are the raw material for the
entire lifecycle — nothing downstream (retrain, gate, promote) can happen
without them. This story delivers standalone value (a cleaner, user-corrected
transaction history) even if no other story ships, and it is the only path that
produces training-grade labels.

**Independent Test**: Sign in, flag a set of transactions as `needs_review`,
open the review queue, correct ten of them, and verify each becomes a
human-confirmed correction in the store while LLM relabels (if the setting is
on) stay quarantined until explicitly confirmed.

**Acceptance Scenarios**:

1. **Given** a user has transactions marked `needs_review`, **When** they open
   the review queue, **Then** only their own flagged rows appear, each with the
   current category and the ability to confirm or change it.
2. **Given** a user changes a transaction's category in the queue, **When** they
   save, **Then** a correction is recorded with provenance `human`, the row's
   category updates, and the row leaves the `needs_review` state.
3. **Given** a user's setting is "automatic relabel", **When** a flagged row is
   processed, **Then** the assistant assigns a category with provenance `llm`,
   the row appears in a quarantine list, and it is excluded from training until a
   human confirms it.
4. **Given** an LLM-relabeled row in quarantine, **When** the user confirms it,
   **Then** its provenance upgrades to `human` and it becomes eligible training
   data.

---

### User Story 2 - Gated retrain with operator promotion (Priority: P2)

As corrections accumulate, the system reaches a retrain trigger (a correction
count, an elapsed-time cooldown, or an operator pressing a manual button). A
training job runs a partial-unfreeze retrain on the accumulated human-confirmed
labels and produces a new candidate model with its model card and content hash.
The candidate (challenger) is scored against the current production model
(champion) on the untouched frozen holdout. Both models' numbers and the
candidate's status are recorded in a model registry. The candidate is never
promoted automatically: an operator reviews the comparison and explicitly
promotes it, after which the serving model reloads to the new artifact.

**Why this priority**: This is the core lifecycle loop and the phase's headline
acceptance criterion (correct rows → trigger → retrain → gate → promote → serve).
It depends on US1's confirmed labels but delivers the central value: the model
measurably improves from human feedback under human control.

**Independent Test**: With at least the demo threshold of confirmed corrections
present, trigger a retrain (manual button), confirm a challenger artifact and its
registry entry are produced with champion-vs-challenger holdout numbers, have an
operator promote the challenger, and verify the serving model now answers from
the new artifact.

**Acceptance Scenarios**:

1. **Given** the count of human-confirmed corrections reaches the trigger
   threshold (production: 100; demo: 10) or the time cooldown (14 days) elapses,
   **When** the trigger is evaluated, **Then** exactly one retrain job is
   enqueued (a duplicate trigger within the same window does not enqueue a second).
2. **Given** a retrain job runs, **When** it completes, **Then** it exports a new
   model artifact, a model card, and a content hash to the artifact store, and
   records a registry entry with status `challenger`.
3. **Given** a challenger exists, **When** it is scored on the frozen holdout,
   **Then** its metrics and the champion's metrics are stored side by side and a
   gate verdict (beats champion / does not) is recorded.
4. **Given** a challenger that beats the champion, **When** a non-operator views
   the ops page, **Then** they cannot promote it; **When** an operator promotes
   it, **Then** the registry marks it `champion`, the previous champion is
   archived, and the serving model reloads to the new artifact.
5. **Given** a challenger that does not beat the champion, **When** the gate
   verdict is recorded, **Then** the promote action is unavailable and the
   champion continues serving unchanged.

---

### User Story 3 - Drift detection and Slack alerting (Priority: P3)

A background monitor watches the live signal of the production model — the
average prediction confidence and the rate at which users correct it (primary
signals), plus the shift in category distribution and the rate of never-before-
seen merchants (secondary signals). When a signal crosses its threshold, the
system raises a drift alarm, posts an ops-only alert to a Slack channel, and
enqueues a retrain. A simulation tool can inject a deliberately skewed batch to
make drift demonstrable on demand. Slack alerts also carry periodic retrain
results and aggregate anomaly-rate statistics — and never contain any individual
user's transaction data.

**Why this priority**: Drift detection closes the loop by deciding *when* the
model needs attention, and the Slack alerting makes the system operable without
someone watching a dashboard. It is the phase's CI gate (#7) and carries the
non-negotiable "no user data in webhook payloads" guarantee.

**Independent Test**: Run the drift-simulation tool to inject a skewed batch,
verify the primary drift signal crosses threshold, a Slack alert is sent, and a
retrain is enqueued — then inspect the alert payload and confirm it contains zero
user-level transaction data.

**Acceptance Scenarios**:

1. **Given** the production model's mean confidence drops below threshold or the
   correction rate rises above threshold, **When** the monitor next evaluates,
   **Then** a drift alarm is raised, a Slack alert is sent, and a retrain is
   enqueued.
2. **Given** the drift-simulation tool injects a skewed held-out-merchant batch,
   **When** the monitor evaluates (on demand), **Then** the unfamiliar merchants
   drive mean confidence below threshold (a primary signal), so drift fires and the
   alarm/alert/retrain sequence occurs (the path used by CI gate #7).
3. **Given** any Slack alert (drift, retrain result, or anomaly-rate summary),
   **When** the payload is inspected, **Then** it contains only operational
   signals and aggregates — no transaction descriptions, amounts, merchants, or
   user identifiers.
4. **Given** the Slack endpoint is slow or unavailable, **When** an alert is
   attempted, **Then** it times out and retries with backoff without blocking or
   failing any user-facing request, and the failure is logged.

---

### User Story 4 - Operator ops dashboard (Priority: P4)

An operator opens an ops page that visualizes the health of the model lifecycle:
confidence and correction-rate charts with their alert thresholds drawn in, the
current drift status, and a retrain history listing each run with its champion-
vs-challenger numbers and outcome. The page also exposes the manual retrain
button and the promote button (active only for an operator, and only when a
promotable challenger exists).

**Why this priority**: The ops page is the human window into US2 and US3. It adds
no new lifecycle capability on its own, so it ranks last, but it is what makes the
loop observable and operable for the demo and for real operations.

**Independent Test**: As an operator, open the ops page and verify it shows the
confidence/correction charts with thresholds, the current drift status, and a
retrain-history table with champion-vs-challenger metrics; confirm the retrain
and promote controls are present and gated to operators.

**Acceptance Scenarios**:

1. **Given** historical confidence and correction-rate data, **When** an operator
   opens the ops page, **Then** both are charted over time with their alert
   thresholds visibly marked.
2. **Given** prior retrain runs, **When** the operator views the history, **Then**
   each run shows its trigger reason, champion and challenger holdout metrics, the
   gate verdict, and the final status.
3. **Given** a non-operator user, **When** they attempt to reach the ops page or
   its controls, **Then** access is denied.

---

### Edge Cases

- **No eligible labels at trigger time**: a trigger fires but there are too few
  human-confirmed corrections to train meaningfully — the system must not produce
  a degenerate model; it records the skipped run with a reason rather than
  enqueuing a doomed job.
- **Concurrent / duplicate triggers**: the count threshold and the manual button
  fire close together — only one retrain job runs for a given window
  (idempotency).
- **Challenger ties the champion**: equal holdout metrics are treated as "does
  not beat" — the champion is retained (no promotion on a tie).
- **Promotion race**: two operators promote near-simultaneously, or a new retrain
  finishes mid-review — the registry must end in one unambiguous champion.
- **Artifact integrity failure**: a promoted artifact's hash does not match on
  reload — serving refuses the swap and keeps the prior champion rather than
  booting a mismatched model.
- **Slack misconfigured**: the webhook secret is missing or invalid — alerts fail
  safe (logged, retried per policy) and never crash the monitor or a user request.
- **User toggles auto-relabel off mid-queue**: rows already auto-relabeled remain
  quarantined and still require confirmation; no retroactive training promotion.
- **Drift simulation in a non-demo context**: the simulation tool's injected batch
  is clearly isolated so it cannot pollute real user data or real training labels.

## Requirements *(mandatory)*

### Functional Requirements

#### Review queue & corrections (US1)

- **FR-001**: The system MUST present each user a review queue of their own
  `needs_review` transactions, scoped to that user only.
- **FR-002**: Users MUST be able to confirm or change the category of a flagged
  transaction; a change MUST record a correction with provenance `human` and
  clear the row's `needs_review` state.
- **FR-003**: The system MUST persist corrections in a durable corrections store
  capturing at least: the transaction, the prior category, the new category, who/
  what set it (provenance), human-confirmation status, and a timestamp.
- **FR-004**: Each user MUST have a setting selecting either manual review or
  automatic LLM relabel for their flagged rows; the default MUST be manual review.
- **FR-005**: When automatic relabel is enabled, the system MUST relabel a flagged
  row with provenance `llm`, surface it in a quarantine list, and EXCLUDE it from
  training data until a human confirms it.
- **FR-006**: A quarantined LLM relabel MUST be confirmed by the user who owns the
  transaction, in their own review queue; confirmation MUST upgrade its provenance
  to `human`, making it eligible training data. Quarantined relabels MUST NOT be
  exposed to operators (no user-level transaction data crosses into the ops view).
- **FR-007**: Only human-confirmed labels MUST ever be used as training data;
  `rule`, `model`, and `llm` provenance labels MUST NOT enter a training set.

#### Retrain trigger & training (US2)

- **FR-008**: The system MUST evaluate a retrain trigger that fires when the count
  of human-confirmed corrections since the last retrain reaches a threshold
  (production 100; demo 10) OR when a time cooldown (14 days) elapses, AND MUST
  expose a manual retrain button for operators.
- **FR-009**: A single global cooldown/idempotency window MUST apply across ALL
  trigger sources (correction count, time cooldown, drift alarm, manual button):
  within one window at most one retrain job is enqueued, regardless of how many
  sources fire. The operator's manual button MUST be able to force-override the
  cooldown and enqueue a retrain immediately.
- **FR-010**: A retrain job MUST run as a heavy, off-the-default-path training
  workload (never inside a request path or a lean serving image) and MUST perform
  a partial-unfreeze retrain on accumulated human-confirmed labels, sized to run
  on CPU.
- **FR-011**: A completed retrain MUST export a new model artifact, a model card,
  and a content hash to the artifact store, and MUST NOT overwrite or discard the
  current champion artifact.
- **FR-012**: A retrain that cannot train meaningfully (insufficient eligible
  labels) MUST be recorded as a skipped run with a reason instead of producing a
  model.

#### Champion/challenger gate & registry (US2)

- **FR-013**: Every model artifact MUST be tracked in a model registry capturing
  at least: artifact location, content hash, evaluation metrics, status (e.g.
  champion / challenger / archived), and creation time.
- **FR-014**: A challenger MUST be scored against the champion on the frozen
  holdout set, which MUST remain untouched by any other process; both models'
  metrics MUST be stored together with a gate verdict.
- **FR-015**: A challenger MUST be promotable ONLY if it beats the champion by the
  configured margin (a tie does NOT beat) AND an operator explicitly approves it.
- **FR-016**: Promotion MUST be restricted to operators (identified by an operator
  flag) and MUST be unavailable to all other users.
- **FR-017**: On promotion, the registry MUST mark the new artifact champion,
  archive the prior champion, and the serving model MUST reload to the new
  artifact; a hash mismatch on reload MUST abort the swap and retain the prior
  champion.

#### Drift monitoring & Slack alerting (US3)

- **FR-018**: A background monitor MUST evaluate the production model's drift
  signals on a once-daily schedule (on the light worker) AND on demand (invocable
  by the drift-simulation tool and CI). It MUST track primary signals — mean
  prediction confidence and correction rate — and secondary signals — category-
  distribution shift (PSI) and new-merchant rate.
- **FR-019**: When a PRIMARY drift signal (mean confidence or correction rate)
  crosses its threshold, the system MUST raise a drift alarm, send a Slack alert,
  AND enqueue a retrain (subject to the FR-009 cooldown). When only a SECONDARY
  signal (PSI or new-merchant rate) crosses, the system MUST raise an alarm and
  send a Slack alert but MUST NOT auto-enqueue a retrain.
- **FR-020**: The system MUST provide a drift-simulation tool that injects a
  skewed held-out-merchant batch to make drift demonstrable, isolated so it cannot
  contaminate real user data or training labels.
- **FR-021**: Slack alerts MUST be sent for drift alarms, retrain results, and
  aggregate anomaly-rate statistics, with the webhook destination resolved from
  the secrets store (never hardcoded).
- **FR-022**: Slack alert payloads MUST contain only operational signals and
  aggregates and MUST NEVER contain user-level transaction data (descriptions,
  amounts, merchants) or user identifiers.
- **FR-023**: Slack delivery MUST have a timeout and retry/backoff, MUST be
  non-blocking with respect to any user-facing request, and MUST log failures
  rather than propagate them.

#### Ops dashboard (US4)

- **FR-024**: The system MUST provide an operator-only ops page showing confidence
  and correction-rate charts with their alert thresholds, the current drift
  status, and a retrain history with per-run champion-vs-challenger metrics, gate
  verdict, and status.
- **FR-025**: The ops page MUST expose the manual retrain control and the promote
  control, both gated so only operators can invoke them and promote is enabled
  only when a promotable challenger exists.

#### Cross-cutting

- **FR-026**: Every lifecycle action that changes state (correction confirmed,
  retrain enqueued/completed, promotion) MUST be observable through structured
  logs/records sufficient to reconstruct the loop after the fact.
- **FR-027**: Each design threshold and cadence introduced by this feature (trigger
  counts, cooldown, drift thresholds, gate margin) MUST be recorded with its
  justifying number in the decisions log.

### Key Entities *(include if feature involves data)*

- **Correction**: A human or LLM relabel of a transaction's category — references
  the transaction and user, the prior and new category, provenance, human-
  confirmation status, and timestamp. The unit that feeds retraining.
- **Review setting (per user)**: The user's choice between manual review and
  automatic LLM relabel for their flagged transactions.
- **Quarantined relabel**: An LLM-assigned category awaiting human confirmation —
  visible to the user, excluded from training, upgradeable to human-confirmed.
- **Model registry entry**: A tracked model artifact — location, content hash,
  holdout metrics, lifecycle status (champion/challenger/archived), trigger origin,
  and timestamps.
- **Retrain run**: A record of a triggered training attempt — trigger reason,
  status (skipped/running/completed/failed), resulting challenger (if any), and the
  champion-vs-challenger comparison.
- **Drift signal record**: A point-in-time measurement of the drift metrics (mean
  confidence, correction rate, PSI, new-merchant rate) with the thresholds in
  effect and whether an alarm fired.
- **Operator**: A user distinguished by an operator flag, authorized to view the
  ops page and invoke retrain/promote.
- **Slack alert**: An outbound operational notification (drift / retrain / anomaly-
  rate) carrying aggregates only.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An operator can run the full loop end to end — correct 10 flagged
  rows, trigger a retrain, see the champion-vs-challenger gate result, promote the
  challenger, and confirm the new model is serving — in a single demo session
  without manual data surgery.
- **SC-002**: 100% of records that enter a training set are human-confirmed; zero
  `rule`/`model`/`llm`-provenance labels appear in any training batch.
- **SC-003**: A simulated drift batch causes the primary drift signal to cross
  threshold, an alert to be sent, and a retrain to be enqueued, 100% of the time
  the simulation is run.
- **SC-004**: 100% of inspected Slack payloads contain zero user-level transaction
  data or user identifiers (verified by an automated test over every alert type).
- **SC-005**: A challenger is promoted to production only when it beats the
  champion on the frozen holdout AND an operator approves; no model reaches
  production through any other path.
- **SC-006**: Duplicate or concurrent retrain triggers within one window produce at
  most one retrain run (no duplicate training jobs).
- **SC-007**: A Slack outage during alerting causes no user-facing request to fail
  or slow beyond its normal budget, and the failure is recorded.
- **SC-008**: Non-operator users cannot reach the ops page or invoke retrain/
  promote — verified by an access-control test.

## Assumptions

- **Foundation training stays offline**: the initial foundation model is trained
  offline (Colab); in-stack retrains are always partial-unfreeze on CPU, never full
  fine-tunes. The "one heavy image" is the trainer; serving images stay lean.
- **Frozen holdout reuse**: the champion/challenger gate reuses the same frozen
  holdout and metric definitions established in the categorizer phase (macro-F1 and
  the existing per-class/threshold rules); this feature does not redefine them.
- **Operator assignment is administrative**: operators are designated by setting an
  operator flag through an administrative/seed path; a self-service "become
  operator" flow is out of scope.
- **Default review mode is manual**: aligning with the human-confirmed-only
  training rule, a user's flagged rows wait for manual review unless they opt into
  automatic LLM relabel.
- **Drift thresholds are configurable; cadence is fixed**: the monitor runs once
  daily plus on demand (clarified 2026-06-17); concrete threshold *numbers* live in
  the central evaluation/config files and are tuned during planning. This spec
  fixes the signals, cadence, and behavior — not the exact threshold numbers.
- **Demo vs production thresholds coexist**: the trigger threshold is 100
  corrections in production and 10 in demo mode, selectable via configuration.
- **Single Slack destination**: one operational Slack channel (incoming webhook)
  receives all alert types; per-alert routing is out of scope.
- **Existing provenance & correction primitives**: the `rule|model|llm|human`
  provenance field and a basic correction-writing path already exist from prior
  phases; this feature builds the queue, store semantics, quarantine, and lifecycle
  around them.

## Dependencies

- Human-confirmed corrections (US1) are a prerequisite for meaningful retrains
  (US2); the ops page (US4) visualizes US2 and US3 and depends on both.
- Requires the existing transaction store with `needs_review` and provenance, the
  artifact store for model artifacts, the secrets store for the Slack webhook, the
  background-worker and training-queue infrastructure, and the lean serving model
  with reload-on-promote capability.

## Out of Scope

- Rails content/policy enforcement, red-teaming, and the data-erasure path (these
  belong to the security & compliance phase).
- Full fine-tunes or GPU training inside the stack.
- A managed experiment-tracking system (a registry table suffices; MLflow-class
  tooling is future work).
- Self-service operator onboarding and multi-channel Slack routing.
