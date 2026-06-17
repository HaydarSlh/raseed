# Implementation Plan: Dashboard UI

**Branch**: `005-dashboard-ui` | **Date**: 2026-06-17 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/005-dashboard-ui/spec.md`

## Summary

Build the React (Vite) SPA pages that consume the already-shipped Phase 3 backend
APIs: an Upload page (`POST /uploads` + manual `POST /transactions`) and a Dashboard
page (`GET /dashboard`) that renders a transaction list, a balance-forecast chart, an
anomalies panel, and subscription cards. Protected routes guard both pages behind the
existing JWT auth. The category badge is read-only this phase — the correction action
and corrections store are deferred to the ML-lifecycle phase (Phase 5) that owns them.
No backend changes.

## Technical Context

**Language/Version**: TypeScript 5.4, React 18.3, targeting ES2020 (existing SPA config).

**Primary Dependencies**: Existing — React 18, Vite 5, `@vitejs/plugin-react`. Added —
`react-router-dom` v6 (routing/guards), `recharts` v2 (forecast chart), `tailwindcss`
v3 + `postcss` + `autoprefixer` (styling). Dev/test — `vitest`, `@testing-library/react`,
`@testing-library/jest-dom`, `jsdom`.

**Storage**: None client-side beyond the existing bearer token in `localStorage`
(`raseed_token`, set in Phase 1). No new client persistence.

**Testing**: Vitest + React Testing Library (jsdom env) for component/render tests;
the existing `tsc --noEmit` type-check and ESLint lint gates remain the primary CI
gates. A `test` step is added to the frontend CI job.

**Target Platform**: Modern desktop browsers (Chromium/Firefox/WebKit current). Layout
is responsive but not mobile-optimized for v1.

**Project Type**: Web application — frontend SPA consuming an existing FastAPI backend.

**Performance Goals**: Dashboard fetches its data once on mount (no polling, no
pagination); render is interactive within typical SPA expectations for a single user's
data volume (tens to low-hundreds of transactions).

**Constraints**: Type-check and lint MUST pass with zero errors and zero warnings
(`npm run typecheck`, `npm run lint --max-warnings 0`). Users never see a stack trace —
all failures surface as readable messages (constitution Art. I). All displayed data is
scoped to the signed-in user via the JWT (constitution Art. II).

**Scale/Scope**: 2 routed pages (Upload, Dashboard) + shared layout/nav + ~6–8
presentational components; one extended API client object (`dashboardApi`).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Art. I — Layered, Async Architecture**: Backend-focused; the only applicable rule
  is "users MUST never see a stack trace." → Satisfied: FR-013 and the error-handling
  edge cases require readable messages on every failure path. No backend layering is
  touched. **PASS**
- **Art. II — Isolation & Data Protection (NON-NEGOTIABLE)**: The SPA sends the JWT on
  every request; the backend derives `user_id` from the token and RLS scopes all reads.
  The UI displays only the signed-in user's data (FR-015). Statement files are uploaded
  to the backend, which parses them in memory and never persists raw bytes — the SPA
  holds the `File` only transiently for the multipart POST and never writes it anywhere.
  No PII crosses an LLM boundary (no LLM in this phase). **PASS**
- **Art. III — ML Lifecycle Integrity**: No model serving or training in the frontend.
  Category provenance (`rule`/`model`) is displayed read-only; the correction action
  (which would create human-confirmed labels) is correctly deferred to Phase 5, keeping
  the "only human-confirmed labels train" pipeline owned by the phase that builds it.
  **PASS**
- **Art. IV — Bounded Agent & Grounded RAG**: No agent, tools, or RAG in this phase.
  The user's numbers come from exact SQL via `GET /dashboard` (not RAG). **PASS**
- **Art. V — Quality & Operations**: Every external (backend) call has error handling
  with a readable failure and a retry affordance (FR-013). The phase ships tests
  (Vitest + RTL) and the CI gates are `typecheck` + `lint` (+ new `test` step), all
  stack-independent — CI never starts the compose stack. **PASS**

**Stack compliance**: React (Vite) SPA is the fixed frontend stack. `react-router-dom`,
`recharts`, and `tailwindcss` are additive libraries within that stack, not
substitutions. **PASS** — no Complexity Tracking entries required.

## Project Structure

### Documentation (this feature)

```text
specs/005-dashboard-ui/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   └── ui-api-contract.md
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created here)
```

### Source Code (repository root)

```text
frontend/
├── src/
│   ├── main.tsx                      # existing — wrap with <BrowserRouter>
│   ├── App.tsx                       # existing — replace shell with <Routes>
│   ├── index.css                     # new — Tailwind directives
│   ├── api/
│   │   ├── client.ts                 # existing — extend with dashboardApi + multipart upload
│   │   └── types.ts                  # new — TransactionView, ForecastView, AnomalyView, SubscriptionView
│   ├── auth/
│   │   └── RequireAuth.tsx           # new — route guard (redirects to /login if no token)
│   ├── components/
│   │   ├── NavBar.tsx                # new — logo + Upload link + Sign out
│   │   ├── UploadDropzone.tsx        # new — file picker / drag-drop
│   │   ├── ManualEntryForm.tsx       # new — date/amount/description form
│   │   ├── ForecastChart.tsx         # new — Recharts line + cold-start notice
│   │   ├── TransactionTable.tsx      # new — list, badges, review/anomaly markers (read-only category)
│   │   ├── AnomaliesPanel.tsx        # new — collapsible anomaly list
│   │   └── SubscriptionsPanel.tsx    # new — subscription cards
│   ├── pages/
│   │   ├── Login.tsx                 # existing — unchanged
│   │   ├── Register.tsx              # existing — unchanged
│   │   ├── Upload.tsx                # new — dropzone + manual form, navigates to /dashboard
│   │   └── Dashboard.tsx            # new — fetches GET /dashboard, composes panels
│   └── test/
│       └── setup.ts                  # new — RTL + jest-dom setup for Vitest
├── tailwind.config.js                # new
├── postcss.config.js                 # new
├── vite.config.ts                    # existing — add Vitest test config (jsdom)
├── package.json                      # existing — add deps + test script
└── .eslintrc.cjs                     # existing — may extend ignore for test setup
```

**Structure Decision**: Web-application frontend. All work lives under `frontend/src/`,
extending the Phase 0 skeleton (`main.tsx`, `App.tsx`, `api/client.ts`, `pages/Login`,
`pages/Register`). New code is organized into `auth/` (guard), `components/`
(presentational), `pages/` (routed containers), and `api/types.ts` (view types). No
backend directories are touched.

## Complexity Tracking

> No constitution violations. No entries required.
