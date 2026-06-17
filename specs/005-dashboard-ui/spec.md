# Feature Specification: Dashboard UI

**Feature Branch**: `005-dashboard-ui`

**Created**: 2026-06-17

**Status**: Draft

**Input**: User description: "briefs/phase-3b-dashboard-ui.md — Wire the React SPA to the Phase 3 backend APIs so a user can upload a bank statement and immediately see a populated dashboard: categorized transactions, a balance forecast, anomaly highlights, and subscription cards. Low-confidence transactions must be visually flagged and correctable in-line."

## Clarifications

### Session 2026-06-17

- Q: Inline category correction needs a corrections endpoint that does not exist, and `docs/PLAN.md` assigns the corrections store + review queue to Phase 5. How should this phase handle it? → A: Defer the correction *action* to Phase 5. This phase displays the needs-review flag, the category source (rule/model), and anomaly highlighting (all already in the dashboard payload), but the category badge is **read-only** — no editing control and no backend writes. The corrections store and review-queue UI are built in the ML-lifecycle phase.
- Q: When a category correction is submitted but the backend request then fails, what should happen to the displayed category? → A: Block until confirmed — the badge does not change until the system confirms the change; a brief loading indicator shows while the request is in flight, and on failure the original category remains with a readable error. No optimistic update. (Applies to Phase 5 when the correction action is built; out of scope here.)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Upload a statement and see results (Priority: P1)

A signed-in user opens the upload page, provides a bank-statement file, and submits
it. The system imports and categorizes the transactions, tells the user how many
were imported and how many need review, and takes them to a dashboard where their
transactions appear.

**Why this priority**: This is the core loop of the product — without it, the user
has no way to get their data into the app or see any value. It is the minimum
viable slice: a user can go from an empty account to seeing their categorized money
in one action.

**Independent Test**: Sign in, upload a known seed statement, and confirm the result
banner reports the correct import count and that the dashboard transaction list is
populated with the uploaded rows and their categories.

**Acceptance Scenarios**:

1. **Given** a signed-in user on the upload page, **When** they select a valid
   statement file and submit, **Then** they see a confirmation reporting the number
   of transactions imported and the number flagged for review, and are taken to the
   dashboard.
2. **Given** a successful upload, **When** the dashboard loads, **Then** the
   uploaded transactions appear in a list sorted with the most recent first, each
   showing its date, description, amount, and assigned category.
3. **Given** a user who is not signed in, **When** they attempt to open the upload
   or dashboard page, **Then** they are redirected to the sign-in page.

---

### User Story 2 - See the balance forecast and spending insights (Priority: P2)

A user with imported history opens the dashboard and sees a projected balance over
the coming weeks, a list of any unusual transactions, and cards for recurring
subscriptions they are paying for.

**Why this priority**: This is the intelligence layer that differentiates the
product from a plain transaction log. It depends on User Story 1 (data must exist
first) but delivers the "insight" value the product promises.

**Independent Test**: With a seeded account holding more than a month of history,
load the dashboard and confirm a forecast line is shown, any anomalous transactions
are listed in the anomalies section, and detected subscriptions appear as cards
with merchant, cadence, and amount.

**Acceptance Scenarios**:

1. **Given** an account with more than a month of transaction history, **When** the
   dashboard loads, **Then** a balance projection over the coming weeks is displayed
   as a chart.
2. **Given** an account with less than a month of history, **When** the dashboard
   loads, **Then** the forecast area shows a clear "not enough history yet" message
   instead of a chart.
3. **Given** transactions that were flagged as unusual, **When** the dashboard
   loads, **Then** those transactions are listed in an anomalies section labeled
   with the kind of anomaly, and are visually distinguished in the main transaction
   list.
4. **Given** the system detected recurring charges, **When** the dashboard loads,
   **Then** each recurring charge appears as a card showing the merchant, how often
   it recurs, and the typical amount, with a marker when its price has increased.

---

### User Story 3 - See which transactions need attention (Priority: P2)

A user scans the dashboard and can immediately tell which transactions the system
was unsure about, which are unusual, and whether each category was assigned by a
rule or by the model — so they know what to trust and what to double-check.

**Why this priority**: Trust is the point of a finance app. Surfacing uncertainty
(needs-review), anomalies, and category provenance lets the user judge the data's
reliability at a glance. It is read-only in this phase; acting on it (editing a
category) is deferred to the ML-lifecycle phase that owns the corrections store.

**Independent Test**: On a populated dashboard, confirm that needs-review
transactions carry a distinct indicator, anomalous rows are visually marked, and
each transaction shows whether its category came from a rule or the model — with no
editing control present.

**Acceptance Scenarios**:

1. **Given** a transaction that needs review, **When** the dashboard displays it,
   **Then** it carries a clear visual indicator distinguishing it from
   confidently-categorized transactions.
2. **Given** a transaction's category, **When** the user views it, **Then** they can
   see whether it was assigned by a rule or by the model.
3. **Given** any transaction in the list, **When** the user views its category,
   **Then** the category is presented read-only with no in-place editing control
   (category correction is deferred to the ML-lifecycle phase).

---

### User Story 4 - Add a single transaction by hand (Priority: P3)

A user who wants to record a one-off transaction not in any statement fills in a
short form with the date, amount, and description and submits it; it is categorized
and added to their history.

**Why this priority**: A useful convenience that exercises the same import path as
the upload, but most data arrives via statements, so it is the lowest priority of
the set.

**Independent Test**: Fill in the manual-entry form with a date, amount, and
description, submit, and confirm the new transaction appears on the dashboard with
an assigned category.

**Acceptance Scenarios**:

1. **Given** the upload page, **When** the user fills in date, amount, and
   description and submits the manual-entry form, **Then** the transaction is
   categorized and added, and the user is taken to the dashboard where it appears.
2. **Given** an incomplete manual-entry form, **When** the user attempts to submit,
   **Then** they are prevented from submitting until the required fields are filled.

---

### Edge Cases

- **Upload of a non-statement or malformed file**: the user sees a readable error
  explaining the file could not be processed, and remains on the upload page able to
  try again.
- **Upload that imports zero new rows** (e.g., all duplicates): the result banner
  states that nothing new was imported rather than implying success with data.
- **Dashboard for a brand-new account with no transactions**: the dashboard shows an
  empty state inviting the user to upload a statement, not broken or blank panels.
- **Backend request fails** (network or server error): because the dashboard loads
  from a single aggregated request, the data area shows one readable error with a
  Retry action while the navigation bar and page shell remain rendered (the page is
  never blank or frozen).
- **Expired or missing session while on a protected page**: the user is returned to
  the sign-in page rather than seeing a silent failure.
- **A transaction with no merchant or an empty description**: it still renders in the
  list without breaking the layout.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The application MUST restrict the upload and dashboard pages to
  signed-in users, redirecting anyone without a valid session to the sign-in page.
- **FR-002**: The application MUST provide a navigation bar on authenticated pages
  with the product name, a link to the upload page, and a sign-out action.
- **FR-003**: Users MUST be able to submit a bank-statement file for import from the
  upload page.
- **FR-004**: After an upload, the application MUST display how many transactions
  were imported and how many were flagged for review.
- **FR-005**: On a successful upload or manual entry, the application MUST take the
  user to the dashboard.
- **FR-006**: Users MUST be able to add a single transaction by entering a date,
  amount, and description, and MUST be prevented from submitting until those fields
  are provided.
- **FR-007**: The dashboard MUST retrieve and display the user's transactions,
  forecast, anomalies, and subscriptions when it loads.
- **FR-008**: The dashboard MUST present transactions as a list ordered with the most
  recent first, each showing date, description, amount, category, the source of the
  category (rule or model), and a review indicator when applicable.
- **FR-009**: The dashboard MUST display the balance forecast as a chart of projected
  balance over the forecast horizon, and MUST instead show a "not enough history"
  notice when the forecast is in its cold-start state.
- **FR-010**: The dashboard MUST list anomalous transactions in a dedicated section
  labeled with the anomaly type, and MUST visually distinguish anomalous rows within
  the main transaction list.
- **FR-011**: The dashboard MUST present each detected subscription as a card showing
  the merchant, recurrence cadence, and typical amount, with a marker when a price
  increase was detected.
- **FR-012**: The dashboard MUST present each transaction's category as read-only and
  MUST NOT offer an in-place category-editing control in this phase. (Writing a
  corrected label is deferred to the ML-lifecycle phase that owns the corrections
  store.)
- **FR-013**: The application MUST show readable error messages when an upload cannot
  be processed or a data request fails, without discarding the rest of the page.
- **FR-014**: The dashboard MUST show an inviting empty state when the account has no
  transactions yet.
- **FR-015**: The application MUST scope all displayed data to the signed-in user
  only.

### Key Entities *(include if feature involves data)*

- **Transaction**: A single money movement shown in the list — has a date, a
  description, an amount, an assigned category, the source of that category (rule or
  model), a review flag, and an anomaly flag.
- **Forecast**: A projection of the user's balance — a series of dated projected
  balance points over a horizon, plus a cold-start indicator meaning there is not yet
  enough history to project.
- **Anomaly**: A flagged transaction with a type describing why it is unusual (for
  example a statistical outlier or a duplicate charge).
- **Subscription**: A detected recurring charge — has a merchant, a cadence (how
  often it recurs), a typical amount, and a price-increase indicator.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A new user can go from the upload page to a populated dashboard in a
  single upload action, with no manual page refresh required.
- **SC-002**: After uploading a statement covering more than a month of history, the
  dashboard displays a forecast chart with at least one projected point.
- **SC-003**: Every transaction that needs review is visually distinguishable from
  confidently-categorized transactions at a glance.
- **SC-004**: For any transaction, a user can tell at a glance whether its category
  was assigned by a rule or by the model and whether it needs review, without opening
  any detail view.
- **SC-005**: When an account has fewer than 30 days of history, the dashboard shows
  the cold-start notice and never a broken or empty chart.
- **SC-006**: All interactive surfaces pass the project's automated type and lint
  checks with zero errors and zero warnings.
- **SC-007**: When a data request fails, the user sees a readable message and a way
  to retry rather than a blank or frozen screen.

## Assumptions

- The Phase 3 backend endpoints for upload (`POST /uploads`), manual transaction
  entry (`POST /transactions`), dashboard retrieval (`GET /dashboard`), forecast
  (`GET /forecast`), and subscriptions (`GET /subscriptions`) already exist and are
  stable; this feature consumes them and adds no backend behavior.
- There is no category-correction endpoint, and building one is out of scope here:
  the corrections store and review-queue UI belong to the ML-lifecycle phase per
  `docs/PLAN.md`. The category badge is therefore read-only in this phase.
- Authentication (sign-in, registration, session token) from the earlier phase is
  reused as-is; this feature only adds an access guard in front of the new pages.
- Statement files are comma-separated exports; the backend owns parsing and
  validation, and the UI surfaces whatever success or error result it returns.
- A single user's data volume is small enough that loading the dashboard data once on
  open (without pagination or live polling) is acceptable for this version.
- Desktop browser is the primary target; a responsive but not mobile-optimized layout
  is acceptable for this version.
- The forecast shows a single projected-balance line; uncertainty bands are out of
  scope for this version.
