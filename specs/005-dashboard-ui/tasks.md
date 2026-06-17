---

description: "Task list for Dashboard UI (Phase 3b)"
---

# Tasks: Dashboard UI

**Input**: Design documents from `specs/005-dashboard-ui/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ui-api-contract.md, quickstart.md

**Tests**: INCLUDED — the constitution (Art. V) requires every phase to ship tests, and
research R4 commits to Vitest + React Testing Library. Test tasks are stack-independent
(backend calls mocked) so CI never starts the compose stack.

**Organization**: Tasks grouped by user story. All paths are under `frontend/` and the
repo-root CI file; no backend code is touched (the APIs already exist).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no incomplete dependencies)
- **[Story]**: US1–US4 maps to the spec's user stories

## Path Conventions

Web app — frontend lives in `frontend/src/`. CI workflow at `.github/workflows/ci.yml`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add the additive libraries, styling, and test tooling the SPA needs.

- [X] T001 Add dependencies and scripts to `frontend/package.json`: runtime `react-router-dom@^6`, `recharts@^2`; styling `tailwindcss@^3`, `postcss`, `autoprefixer`; dev/test `vitest`, `@testing-library/react`, `@testing-library/jest-dom`, `@testing-library/user-event`, `jsdom`. Add scripts `"test": "vitest run"` and `"test:watch": "vitest"`. Run `npm install`.
- [X] T002 [P] Configure Tailwind: create `frontend/tailwind.config.js` (content globs `./index.html`, `./src/**/*.{ts,tsx}`), `frontend/postcss.config.js` (tailwindcss + autoprefixer), `frontend/src/index.css` with the three `@tailwind` directives, and import `'./index.css'` in `frontend/src/main.tsx`.
- [X] T003 [P] Configure Vitest: add a `test` block (`environment: 'jsdom'`, `globals: true`, `setupFiles: './src/test/setup.ts'`) to `frontend/vite.config.ts`, and create `frontend/src/test/setup.ts` importing `@testing-library/jest-dom`. Add the `vitest/globals` + `jest-dom` types to `frontend/tsconfig.json` if needed for type-check.
- [X] T004 [P] Add a `Test` step running `npm run test` to the `frontend` job in `.github/workflows/ci.yml` (after the Lint step).

**Checkpoint**: `npm run dev`, `npm run typecheck`, `npm run lint`, `npm run test` all run (test suite empty but green).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared types, API client, routing, guard, nav, and the two page shells every
story builds on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T005 [P] Create view types in `frontend/src/api/types.ts`: `TransactionView`, `ForecastPointView`, `ForecastView`, `AnomalyView`, `SubscriptionView`, `DashboardView`, `UploadResultView`, `ManualEntryInput`, `ManualTransactionResultView` — mirroring the shapes in `contracts/ui-api-contract.md` and `data-model.md`.
- [X] T006 Extend `frontend/src/api/client.ts` with a `dashboardApi` object: `getDashboard()` → GET `/dashboard`, `getForecast()` → GET `/forecast`, `getSubscriptions()` → GET `/subscriptions`, `addTransaction(input)` → POST `/transactions`, and `uploadStatement(file)` → POST `/uploads` building `FormData` and calling `fetch` directly with only the `Authorization` header (bypassing the JSON `apiFetch`, per research R5). Map non-2xx to readable errors using the backend `detail`. (Depends on T005.)
- [X] T007 [P] Create the route guard `frontend/src/auth/RequireAuth.tsx`: render children when `raseed_token` is in `localStorage`, else `<Navigate to="/login" replace>`.
- [X] T008 [P] Create `frontend/src/components/NavBar.tsx`: product name, a link to `/upload`, and a Sign-out action that clears `raseed_token` and routes to `/login`.
- [X] T009 [P] Wrap the app in `<BrowserRouter>` in `frontend/src/main.tsx`.
- [X] T010 [P] Create the Dashboard page shell `frontend/src/pages/Dashboard.tsx`: on mount call `dashboardApi.getDashboard()`, hold loading / error / empty / loaded state, render `<NavBar>` plus titled section slots for forecast, transactions, anomalies, and subscriptions, an empty state (FR-014), an error state with retry (FR-013/SC-007), and a Refresh button that re-fetches (research R6). (Depends on T006, T008.)
- [X] T011 [P] Create the Upload page shell `frontend/src/pages/Upload.tsx`: render `<NavBar>`, slots for the dropzone and the manual form, and a result-banner area; expose an `onSuccess` that navigates to `/dashboard`. (Depends on T006, T008.)
- [X] T012 Replace the shell in `frontend/src/App.tsx` with `<Routes>`: `/login` and `/register` (existing pages), `/upload` and `/dashboard` each wrapped in `<RequireAuth>`, and `/` redirecting to `/dashboard`. (Depends on T007, T010, T011.)
- [X] T013 [P] Test the guard in `frontend/src/auth/RequireAuth.test.tsx`: no token → redirects to `/login`; token present → renders children (FR-001). (Depends on T007.)

**Checkpoint**: App routes; protected pages redirect when signed out; Dashboard fetches and shows loading/empty/error states.

---

## Phase 3: User Story 1 - Upload a statement and see results (Priority: P1) 🎯 MVP

**Goal**: A signed-in user uploads a statement, sees an import-result banner, and lands on
a dashboard listing the imported transactions.

**Independent Test**: Sign in, upload a seed CSV, confirm the banner reports import counts
and the dashboard transaction list is populated newest-first.

### Tests for User Story 1

- [X] T014 [P] [US1] Test `UploadDropzone` in `frontend/src/components/UploadDropzone.test.tsx`: selecting a file and submitting calls `dashboardApi.uploadStatement` (mocked) and renders the result banner "N imported, M flagged for review"; the zero-import case renders the "nothing new imported" message.
- [X] T015 [P] [US1] Test `TransactionTable` basic render in `frontend/src/components/TransactionTable.test.tsx`: given transactions, rows appear sorted by `txn_date` descending showing date, description, amount, and a category badge.

### Implementation for User Story 1

- [X] T016 [P] [US1] Create `frontend/src/components/UploadDropzone.tsx`: file picker + drag-and-drop for `.csv`, submit calls `dashboardApi.uploadStatement`, surfaces the `UploadResultView` banner and readable upload errors (413/422).
- [X] T017 [US1] Wire `UploadDropzone` and the result banner into `frontend/src/pages/Upload.tsx`; on success invoke `onSuccess` to navigate to `/dashboard`. (Depends on T016, T011.)
- [X] T018 [P] [US1] Create `frontend/src/components/TransactionTable.tsx`: render transactions sorted by `txn_date` desc with columns date, description, amount, and a read-only category badge ("uncategorized" when null).
- [X] T019 [US1] Wire `TransactionTable` into the transactions slot of `frontend/src/pages/Dashboard.tsx`. (Depends on T018, T010.)

**Checkpoint**: Upload → banner → dashboard list works end-to-end. MVP demonstrable.

---

## Phase 4: User Story 2 - See the balance forecast and spending insights (Priority: P2)

**Goal**: The dashboard shows a balance-forecast chart (or cold-start notice), an anomalies
panel, and subscription cards.

**Independent Test**: With > 30 days of seeded history, the forecast chart renders ≥ 1
point; anomalies are listed by type; subscriptions render as cards.

### Tests for User Story 2

- [X] T020 [P] [US2] Test `ForecastChart` in `frontend/src/components/ForecastChart.test.tsx`: `is_cold_start: true` (or empty points) renders the "not enough history yet" notice; populated points render the chart container.
- [X] T021 [P] [US2] Test `AnomaliesPanel` and `SubscriptionsPanel` in `frontend/src/components/AnomaliesPanel.test.tsx` and `frontend/src/components/SubscriptionsPanel.test.tsx`: anomalies list with their type labels; subscription cards show merchant/cadence/amount and the price-increase badge when true.

### Implementation for User Story 2

- [X] T022 [P] [US2] Create `frontend/src/components/ForecastChart.tsx`: Recharts `LineChart` of `projected_balance` over `date`; render the cold-start notice when `is_cold_start` or `points` is empty.
- [X] T023 [P] [US2] Create `frontend/src/components/AnomaliesPanel.tsx`: collapsible section listing anomalies with a human label per `anomaly_type` and the `reason`.
- [X] T024 [P] [US2] Create `frontend/src/components/SubscriptionsPanel.tsx`: one card per subscription (merchant, cadence, typical amount, next charge date) with a "price increased" badge when `price_increase`.
- [X] T025 [US2] Wire `ForecastChart`, `AnomaliesPanel`, and `SubscriptionsPanel` into their slots in `frontend/src/pages/Dashboard.tsx`, and confirm the Refresh button re-fetches all panels (research R6). (Depends on T022, T023, T024, T010.)

**Checkpoint**: Dashboard shows forecast/anomalies/subscriptions; cold-start handled.

---

## Phase 5: User Story 3 - See which transactions need attention (Priority: P2)

**Goal**: Surface trust signals on the transaction list — needs-review indicator,
rule/model provenance, anomaly highlight — with the category strictly read-only.

**Independent Test**: On a populated dashboard, needs-review rows carry a distinct
indicator, anomalous rows are highlighted, each row shows its category source, and the
category badge has no editing control.

### Tests for User Story 3

- [X] T026 [P] [US3] Extend `frontend/src/components/TransactionTable.test.tsx`: needs-review rows show the review indicator; rows show a `rule`/`model` provenance chip; `is_anomaly` rows are visually marked; the category badge exposes no button/select/edit affordance (FR-012).

### Implementation for User Story 3

- [X] T027 [US3] Enhance `frontend/src/components/TransactionTable.tsx`: add a needs-review indicator, a rule/model provenance chip, an anomaly row highlight, and keep the category badge read-only (no edit control). (Depends on T018.)

**Checkpoint**: Trust signals visible; category confirmed read-only (correction deferred to Phase 5).

---

## Phase 6: User Story 4 - Add a single transaction by hand (Priority: P3)

**Goal**: A manual-entry form on the upload page adds one categorized transaction.

**Independent Test**: Fill date/amount/description and submit → transaction appears on the
dashboard; submitting with a blank required field is blocked; a duplicate shows a readable
message.

### Tests for User Story 4

- [X] T028 [P] [US4] Test `ManualEntryForm` in `frontend/src/components/ManualEntryForm.test.tsx`: submit is disabled until date, amount (non-zero), and description are present; a valid submit calls `dashboardApi.addTransaction` (mocked); a `409` surfaces an "already recorded" message.

### Implementation for User Story 4

- [X] T029 [P] [US4] Create `frontend/src/components/ManualEntryForm.tsx`: fields date, amount, description, optional merchant, currency (default GBP); submit disabled until required fields present (FR-006); submit calls `dashboardApi.addTransaction`; handle the `409` duplicate and `422` validation responses with readable messages.
- [X] T030 [US4] Wire `ManualEntryForm` into `frontend/src/pages/Upload.tsx`; on success navigate to `/dashboard`. (Depends on T029, T011.)

**Checkpoint**: All four stories independently functional.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T031 [P] Empty-state and error-handling consistency pass across all Dashboard panels and the Upload page — one failing panel never blanks the page; every failure shows a readable message and retry (FR-013, FR-014, SC-007).
- [X] T032 [P] Audit for leaked stack traces and hardcoded values in `frontend/src/`: all user-facing failures are readable strings; the API base URL comes from `import.meta.env` (no hardcoded hosts beyond the documented fallback).
- [X] T033 Run `npm run typecheck`, `npm run lint`, and `npm run test` in `frontend/`; fix until all three are zero-error / zero-warning / green (SC-006).
- [X] T034 [P] Append a Phase 3b section to `docs/DECISIONS.md` recording: (1) deferring category correction + corrections store to Phase 5 (no `/corrections` endpoint; `docs/PLAN.md` ownership), (2) frontend test tooling = Vitest + React Testing Library (stack-independent CI), (3) single aggregated `GET /dashboard` fetch + manual Refresh for recompute eventual-consistency (research R6). Per constitution Art. V.
- [X] T035 Run `specs/005-dashboard-ui/quickstart.md` scenarios 1–7 against the live stack; confirm each acceptance criterion.
- [X] T036 [P] Refresh the knowledge graph with `graphify update .` per the constitution workflow.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies — start immediately. T002/T003/T004 parallel after T001.
- **Foundational (Phase 2)**: depends on Setup — BLOCKS all user stories.
- **User Stories (Phase 3–6)**: all depend on Foundational. US1, US2, US4 are mutually
  independent. **US3 depends on US1** (it enhances the `TransactionTable.tsx` that US1
  creates) — sequence US3 after US1.
- **Polish (Phase 7)**: depends on all desired stories complete.

### Within Each User Story

- Tests are written first and expected to fail before implementation.
- Components (different files, [P]) before the page-wiring task that composes them.
- Page-wiring tasks are sequential (they edit a shared page file).

### Parallel Opportunities

- Setup: T002, T003, T004 in parallel after T001.
- Foundational: T005 first; then T007, T008, T009 in parallel; T010, T011 in parallel after T006+T008; T013 after T007; T012 last (composes pages + guard).
- US1: T014, T015 (tests) parallel; T016, T018 (components) parallel; then T017, T019 wire-in.
- US2: T020, T021 (tests) parallel; T022, T023, T024 (components) parallel; then T025 wire-in.
- US4: T028 test; T029 component; T030 wire-in.
- Polish: T031, T032, T034, T036 parallel; T033 then T035 sequential at the end.

---

## Parallel Example: User Story 2

```bash
# Tests for US2 together:
Task: "Test ForecastChart in frontend/src/components/ForecastChart.test.tsx"
Task: "Test AnomaliesPanel/SubscriptionsPanel in frontend/src/components/*.test.tsx"

# Components for US2 together (different files):
Task: "Create frontend/src/components/ForecastChart.tsx"
Task: "Create frontend/src/components/AnomaliesPanel.tsx"
Task: "Create frontend/src/components/SubscriptionsPanel.tsx"
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 Setup → 2. Phase 2 Foundational → 3. Phase 3 US1 → **STOP and validate**:
   upload a seed CSV and confirm the dashboard lists the transactions. Demo-able MVP.

### Incremental Delivery

Foundational → US1 (MVP: upload + list) → US2 (forecast + insights) → US3 (trust signals)
→ US4 (manual entry) → Polish. Each story adds value without breaking the previous.

### Notes

- [P] = different files, no incomplete dependencies.
- US3 is the one intentional intra-feature dependency (enhances US1's table) — noted above.
- No backend tasks: the Phase 3 APIs already exist; this feature only consumes them.
- Category correction is deferred to Phase 5 (no `/corrections` endpoint, no edit control).
- Commit after each task or logical group; stop at any checkpoint to validate a story.
