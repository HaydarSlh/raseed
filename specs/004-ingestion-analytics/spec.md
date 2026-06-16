# Feature Specification: Statement Ingestion & Financial Analytics

**Feature Branch**: `004-ingestion-analytics`

**Created**: 2026-06-16

**Status**: Draft

**Input**: User description: "briefs/phase-3-ingestion-analytics.md — A user uploads a statement and lands on a dashboard showing categorized transactions, a projected balance with a likely range, anomalies, and subscriptions."

## Clarifications

### Session 2026-06-16

- Q: Which statement file formats does v1 ingest? → A: Delimited statement exports (CSV-class). Arbitrary-PDF parsing is deferred to future work.
- Q: What forward horizon does the dashboard projection cover? → A: 30 days.
- Q: When does the cold-start fallback apply instead of the per-user forecast? → A: When the user has fewer than 30 days of transaction history.
- Q: How are transactions de-duplicated across re-uploads / overlapping statements? → A: By a natural key — (user, date, amount, normalized description); a row matching an existing key is not re-inserted.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Upload a statement and see categorized transactions (Priority: P1)

A user uploads a bank statement and is taken to a dashboard where every transaction
is listed with an assigned spending category. Transactions the system is confident
about are categorized automatically; the rest are clearly flagged as needing review.

**Why this priority**: This is the core value of the phase and the minimum viable
slice — without trustworthy categorized transactions, none of the downstream views
(projection, anomalies, subscriptions) have anything to stand on. It is demonstrable
on its own.

**Independent Test**: Upload a seed statement and confirm the dashboard lists each
transaction with a category and a provenance/confidence indicator, with low-confidence
rows marked for review — no forecast or detector output required.

**Acceptance Scenarios**:

1. **Given** a signed-in user with no transactions, **When** they upload a supported
   statement file, **Then** the dashboard shows each parsed transaction with a category
   and the raw file is not retained anywhere.
2. **Given** a transaction whose merchant matches a known rule, **When** it is ingested,
   **Then** it is categorized deterministically and marked as rule-sourced.
3. **Given** a transaction the categorizer scores below its category's confidence
   threshold, **When** it is ingested, **Then** it is stored and visibly marked
   `needs_review` rather than silently auto-accepted.
4. **Given** a statement containing card/account numbers, **When** it is parsed, **Then**
   those identifiers are scrubbed before anything is stored.

---

### User Story 2 - See a projected balance with a likely range (Priority: P2)

The dashboard shows the user a projected account balance over an upcoming period,
presented as a likely range rather than a single deceptive number, so they can
anticipate cash-flow before it happens.

**Why this priority**: The projection is the headline analytic that differentiates the
product, but it depends on US1 producing categorized history first.

**Independent Test**: With a seeded transaction history, open the dashboard and confirm
a projected balance is shown together with an upper/lower likely range over the
projection horizon, and that the projection is more accurate than a naive day-of-week
baseline on a fixed evaluation dataset.

**Acceptance Scenarios**:

1. **Given** a user with sufficient history, **When** they view the dashboard, **Then**
   they see a projected balance and a likely range covering the projection horizon.
2. **Given** a user with little or no history (cold start), **When** they view the
   dashboard, **Then** they still see a sensible projection derived from typical patterns
   rather than an error or an empty state.
3. **Given** known recurring income and bills, **When** the projection is produced,
   **Then** those known items are projected deterministically and only variable
   discretionary spending is estimated.

---

### User Story 3 - Surface anomalies and subscriptions (Priority: P3)

The dashboard highlights unusual transactions (anomalies) and recurring charges
(subscriptions), including when a recurring charge appears to have increased in price.

**Why this priority**: High-value insight, but additive on top of categorized history;
the product is still useful without it.

**Independent Test**: With a seeded history that contains an obvious outlier, a duplicate
charge, and a monthly subscription, confirm the dashboard flags the outlier and duplicate
as anomalies and lists the subscription with its cadence and next expected charge.

**Acceptance Scenarios**:

1. **Given** a transaction far outside the user's normal range for its category or
   merchant, **When** the dashboard loads, **Then** it is flagged as an anomaly.
2. **Given** two near-identical charges in a short window, **When** detection runs,
   **Then** the duplicate is flagged.
3. **Given** a charge that recurs on a regular cadence, **When** detection runs, **Then**
   it is listed as a subscription with its cadence and next expected charge date, and a
   price increase is flagged when the amount rises.

---

### User Story 4 - Add a single transaction manually (Priority: P3)

A user enters a single transaction through a form (e.g., a cash purchase the bank
statement never captured) and it flows through exactly the same categorization and
enrichment as an uploaded statement.

**Why this priority**: A convenience entry point that reuses the ingestion path; valuable
but not required for the core upload-to-dashboard journey.

**Independent Test**: Submit the manual form for one transaction and confirm it appears
on the dashboard categorized and enriched identically to an uploaded row, and that
derived views update to include it.

**Acceptance Scenarios**:

1. **Given** a signed-in user, **When** they submit the single-transaction form, **Then**
   the transaction is categorized and stored through the same path as an uploaded one.
2. **Given** a newly added transaction, **When** it is stored, **Then** the projection,
   anomalies, and subscriptions recompute to reflect the updated history.

### Edge Cases

- What happens when an uploaded file is empty, malformed, or in an unsupported format?
  The system rejects it with a clear message and stores nothing.
- How does the system handle a user with too little history to forecast? It falls back to
  a cold-start projection blending typical day-of-week patterns with an anonymized
  population prior.
- What happens when the categorization service is unavailable mid-ingestion? Ingestion
  fails safe without partially persisting unscrubbed or uncategorized rows.
- How are duplicate uploads of the same statement handled? Re-ingestion matches the natural
  key (user, date, amount, normalized description) and does not re-insert already-present
  transactions, so overlapping statements do not create divergent duplicate history.
- What happens to derived views (projection/anomalies/subscriptions) when history
  changes? They are invalidated and recomputed; a read never returns stale derived data
  silently.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a single shared ingestion path that accepts both an
  uploaded statement and a manually entered single transaction and processes both
  identically.
- **FR-002**: The system MUST parse uploaded statements in memory and MUST NOT persist the
  raw uploaded bytes in any store.
- **FR-003**: The system MUST scrub card numbers (PAN) and account numbers (IBAN) during
  parsing, before any transaction data is stored.
- **FR-004**: The system MUST first apply a deterministic rules layer (e.g., known-merchant
  lookup); rule-matched transactions MUST be recorded with rule provenance and full
  confidence.
- **FR-005**: For transactions not resolved by rules, the system MUST obtain a category and
  confidence from the categorization service.
- **FR-006**: The system MUST apply a confidence gate per the categorizer's committed
  per-category thresholds: at/above threshold the transaction is accepted with model
  provenance; below threshold it is stored and marked `needs_review`.
- **FR-007**: Every stored transaction MUST carry its category, a confidence value, and a
  provenance label (rule | model | human).
- **FR-008**: The system MUST persist enriched transactions scoped strictly to the owning
  user; no user may read another user's transactions.
- **FR-009**: The system MUST produce a per-user balance projection over a 30-day forward
  horizon, decomposed so that known recurring income and bills are projected
  deterministically and only variable discretionary spending is estimated.
- **FR-010**: The projection MUST be presented as a likely range (lower/upper bound), not
  only a single point value.
- **FR-011**: The forecasting approach MUST beat a day-of-week baseline on error (MAE) on a
  committed evaluation dataset.
- **FR-012**: For users with fewer than 30 days of transaction history (cold start), the
  system MUST produce a projection blending day-of-week averages with an anonymized
  population prior, rather than the per-user forecast.
- **FR-013**: The population prior MUST be computed by a privileged background process into
  a global anonymized statistics store; ordinary user-scoped sessions MUST NOT compute
  cross-user aggregates.
- **FR-014**: The system MUST detect anomalous transactions using a robust per-category and
  per-merchant statistical rule plus a duplicate-charge rule.
- **FR-015**: The system MUST detect recurring charges (subscriptions), reporting cadence
  and next expected charge, and MUST flag apparent price increases.
- **FR-016**: Derived data (projection, anomalies, subscriptions) MUST be invalidated and
  recomputed when a user's transaction history changes; reading a projection MUST be a
  stored-data read, not an on-demand recomputation.
- **FR-017**: The system MUST present a dashboard showing categorized transactions, the
  projection with its likely range, anomalies, and subscriptions, and MUST visibly mark
  `needs_review` transactions.
- **FR-018**: The system MUST provide an upload page and a single-transaction entry form.
- **FR-019**: The system MUST ingest delimited statement exports (CSV-class); arbitrary-PDF
  parsing is out of scope for v1.
- **FR-020**: The system MUST de-duplicate transactions by the natural key (user, date,
  amount, normalized description) so that re-uploading a statement or uploading overlapping
  statements does not create divergent duplicate history.

### Key Entities *(include if feature involves data)*

- **Transaction (enriched)**: a single financial movement for one user — date, amount,
  description, assigned category, confidence, provenance, and review/anomaly flags.
- **Projection**: a per-user forecast of balance over the horizon, including the likely
  range bounds and the decomposition into known vs. estimated components.
- **Anomaly**: a reference to a transaction flagged as unusual, with the reason (statistical
  outlier or duplicate).
- **Subscription (recurring series)**: a detected recurring charge — merchant, cadence,
  typical amount, next expected charge, and price-increase indicator.
- **Population prior**: an anonymized, aggregated statistics record used only as a
  cold-start fallback; contains no user-identifying data.
- **Ingestion batch**: the transient in-memory representation of an upload; exists only
  during processing and is never persisted in raw form.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: From a seed statement, a signed-in user reaches a populated dashboard
  (categorized transactions, projection with range, anomalies, subscriptions) end-to-end
  in a single session with no manual data fixes.
- **SC-002**: The forecaster's error (MAE) is less than or equal to the day-of-week
  baseline's on the committed evaluation dataset.
- **SC-003**: An automated test proves that no raw uploaded file bytes are persisted in any
  store after ingestion.
- **SC-004**: 100% of transactions scoring below their category threshold are visibly
  marked `needs_review` on the dashboard.
- **SC-005**: No user-scoped operation returns or aggregates another user's data; the only
  cross-user aggregate is the anonymized population prior produced by the privileged job.
- **SC-006**: After a transaction is added or a statement re-ingested, the projection,
  anomalies, and subscriptions reflect the updated history on the next dashboard view.
- **SC-007**: The projection always presents an explicit likely range, including in the
  cold-start case.

## Assumptions

- **Reused foundations**: Authentication, per-user isolation (row-level security), and the
  async service/repository structure from the foundation phase are in place and reused; the
  categorization service from the previous phase is called over the internal network.
- **Confidence threshold source**: The confidence gate reuses the categorizer's committed
  per-category operating thresholds rather than introducing a new global threshold.
- **Statement formats**: v1 ingests delimited statement exports (CSV-class). Broad
  arbitrary-PDF parsing is out of scope for v1 and treated as a future extension.
  *(Confirmed in clarification 2026-06-16.)*
- **Projection horizon**: The dashboard projection covers a 30-day forward horizon, and the
  cold-start fallback applies below 30 days of history. *(Confirmed in clarification
  2026-06-16.)*
- **Recurring income**: v1 assumes recurring income; variable-income forecasting is future
  work.
- **Evaluation dataset**: The forecaster CI gate runs against a committed fixture dataset
  (golden forecasting fixture); CI never requires the live database.
- **Dashboard surface**: The dashboard and upload/entry pages extend the existing web
  single-page application.

## Out of Scope

- Conversational/agent interactions and the review-queue management UI (later phases).
- Retrieval-augmented financial-literacy answers (later phase).
- Variable-income forecasting and external bank-sync integrations (future work).
- Global cross-user predictive models beyond the anonymized cold-start prior.
