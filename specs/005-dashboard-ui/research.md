# Research: Dashboard UI

Phase 0 decisions. The Technical Context had no hard `NEEDS CLARIFICATION` blockers
(the spec's one open item — accessibility — is explicitly deferred), so research here
pins down the additive library and testing choices and how they fit the fixed stack.

## R1 — Routing & route guarding

**Decision**: `react-router-dom` v6 with a `<RequireAuth>` wrapper component that checks
for `raseed_token` in `localStorage` and `<Navigate to="/login" replace>` when absent.
Routes: `/login`, `/register` (public, existing pages), `/upload`, `/dashboard`
(protected). Default `/` redirects to `/dashboard`.

**Rationale**: v6 is the current standard, tiny, and its `<Navigate>` + nested-route
model expresses the guard declaratively without a state library. The token already
lives in `localStorage` (Phase 1 `authApi`), so the guard is a synchronous read — no
async auth context needed for v1.

**Alternatives considered**: TanStack Router (heavier, overkill for 4 routes); hand-rolled
conditional rendering in `App.tsx` (no URL history, breaks deep-linking and the
"redirect to login" acceptance scenario).

## R2 — Forecast chart

**Decision**: `recharts` v2 `LineChart` plotting `projected_balance` against `date`
over the 30-point horizon. When `forecast.is_cold_start` is true (or `points` is empty),
render a "not enough history yet" notice instead of the chart.

**Rationale**: Recharts is declarative, React-native (SVG components, no imperative
canvas), and reads an array of `{date, projected_balance}` objects directly from the
`GET /dashboard` payload. A single line matches the spec (uncertainty bands are out of
scope, though the payload also carries `lower`/`upper` should a later phase want them).

**Alternatives considered**: Chart.js (imperative, needs a React wrapper and refs);
visx (lower-level, more code for a single line); hand-rolled SVG (reinvents axes/ticks).

## R3 — Styling

**Decision**: Tailwind CSS v3 via PostCSS, with `index.css` holding the three
`@tailwind` directives and `tailwind.config.js` scanning `index.html` and `src/**/*.tsx`.

**Rationale**: Utility-first keeps styling co-located with markup, no component-library
weight, and gives consistent spacing/colour tokens for badges (category, provenance,
needs-review amber, anomaly highlight) without bespoke CSS files. Matches the brief.

**Alternatives considered**: A component library (MUI/Chakra — too heavy, opinionated,
contradicts "clean and minimal data app"); plain CSS modules (more files, manual design
tokens); CSS-in-JS (runtime cost, extra dep).

## R4 — Frontend testing

**Decision**: Vitest + React Testing Library (`@testing-library/react`,
`@testing-library/jest-dom`) in a `jsdom` environment, configured inside the existing
`vite.config.ts` (`test` block) with a `src/test/setup.ts`. Backend calls are stubbed by
mocking the `api/client` module (or `global.fetch`) so tests stay stack-independent.
Add `"test": "vitest run"` to `package.json` scripts and a `test` step to the frontend
CI job.

**Rationale**: Constitution Art. V requires every phase to ship tests and CI to never
depend on the running stack. Vitest reuses the Vite config/transform pipeline (no
separate Jest/babel toolchain), and RTL tests assert user-visible behaviour (badges,
cold-start notice, error/empty states) rather than implementation detail. Mocking the
client keeps tests deterministic and offline.

**Alternatives considered**: Jest (separate config, slower with Vite, needs ts-jest/babel);
Playwright/Cypress E2E (valuable but needs the live stack — violates stack-independent CI;
better suited to the `quickstart.md` manual run); no tests (violates Art. V).

**Test scope (proportionate)**: render/behaviour tests for the highest-signal surfaces —
`RequireAuth` redirect, `ForecastChart` cold-start vs populated, `TransactionTable`
review/anomaly/provenance markers and read-only category, `AnomaliesPanel` /
`SubscriptionsPanel` rendering, and the upload result banner ("N imported, M flagged").

## R5 — Multipart upload from the SPA

**Decision**: `dashboardApi.uploadStatement(file)` builds a `FormData` with the `File`
under the field name `file` and POSTs to `/uploads` with **only** the `Authorization`
header — letting the browser set the `multipart/form-data` boundary automatically. It
does **not** send `Content-Type: application/json`.

**Rationale**: The backend `POST /uploads` signature is `file: UploadFile`, i.e. FastAPI
expects a multipart field named `file`. The existing `apiFetch` helper forces
`Content-Type: application/json`, which would corrupt a multipart body — so the upload
call must bypass that helper and call `fetch` directly (mirroring how `authApi.login`
already bypasses it for form-encoded login). Backend returns `202` with
`{ingested, needs_review, duplicates_skipped, recompute_enqueued}`.

**Alternatives considered**: Reusing `apiFetch` (breaks multipart — wrong content-type);
base64-encoding into a JSON body (backend doesn't accept it; wasteful).

## R6 — Recompute latency after upload (eventual consistency)

**Decision**: After a successful upload (HTTP 202), navigate to `/dashboard` and fetch
once. Because `POST /uploads` enqueues the recompute job asynchronously, forecast /
anomalies / subscriptions may lag the transaction insert by worker latency. The
dashboard therefore treats an empty forecast as the cold-start/empty state and provides
a manual "Refresh" affordance so the user can re-fetch after the worker finishes. No
polling.

**Rationale**: Matches the backend's invalidate-on-write design (constitution Art. V)
without introducing client-side polling complexity. Transactions appear immediately
(synchronous insert); derived panels fill in on the next fetch. A single Refresh button
is the minimal honest UX for the eventual-consistency window.

**Alternatives considered**: Polling `GET /dashboard` on an interval (wasteful, fights
the "load once" assumption); websockets/SSE (no backend support, out of scope);
blocking the upload response on recompute (backend deliberately returns 202 — would
require backend changes).

## R7 — Category taxonomy for display

**Decision**: Display whatever `category` string the dashboard payload returns; no local
taxonomy list is needed this phase because the badge is read-only (correction action
deferred to Phase 5). Render unknown/empty categories as a neutral "uncategorized" badge.

**Rationale**: With editing deferred, the UI never needs the full category enum — it only
renders the assigned string. This removes a coupling to the backend taxonomy file and a
whole class of "list drifts from backend" bugs for this phase.

**Alternatives considered**: Bundling the taxonomy YAML into the frontend (needed only
for the deferred correction dropdown — premature here).
