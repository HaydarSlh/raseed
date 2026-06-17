# Phase 3b — Dashboard UI

## Intent
Wire the React SPA to the Phase 3 backend APIs so a user can upload a bank
statement and immediately see a populated dashboard: categorized transactions,
a 30-day balance forecast chart, anomaly highlights, and detected subscription
cards. Low-confidence transactions must be visually flagged and correctable in-line.

## In scope (deliverables)

### Routing & layout
- React Router v6 with two protected routes: `/upload` and `/dashboard`.
- Auth guard: redirect to `/login` if no token in localStorage.
- Shared nav bar: logo + "Upload" link + "Sign out" button.

### Upload page (`/upload`)
- Drag-and-drop zone OR file picker for `.csv` files.
- On submit: `POST /uploads` (multipart), show a result banner
  ("5 imported, 2 flagged for review").
- Manual-entry form below: date, amount, description → `POST /transactions`.
- Both actions navigate to `/dashboard` on success.

### Dashboard page (`/dashboard`)
Fetches `GET /dashboard` once on mount (no polling).

**Forecast panel** — Recharts `LineChart`:
- X-axis: date, Y-axis: projected balance.
- Single line for `projected_balance`. Cold-start state shows a "not enough
  history" notice instead of the chart.

**Transaction list** — table sorted by date desc:
- Columns: date, description, amount, category badge, provenance chip
  (`rule` / `model`), `needs_review` warning icon.
- Inline category correction: click the badge → dropdown of taxonomy categories
  → `POST /corrections` with `{transaction_id, corrected_label}`.
- Anomalous rows highlighted in amber.

**Anomalies panel** — collapsible section listing flagged transactions with
anomaly type label (`statistical_outlier` / `duplicate_charge`).

**Subscriptions panel** — cards: merchant, cadence, typical amount, price-increase
badge if applicable.

### API additions in client.ts
```
dashboardApi.getDashboard() → GET /dashboard
dashboardApi.getSubscriptions() → GET /subscriptions
dashboardApi.uploadStatement(file: File) → POST /uploads (multipart)
dashboardApi.addTransaction(row) → POST /transactions
dashboardApi.correctCategory(txnId, label) → POST /corrections
```

### Styling
Tailwind CSS v3 (utility-first; no component library). Keep it clean and minimal
— this is a data app, not a marketing site.

## Out of scope
- Agent chat UI (Phase 4).
- Notifications / alert inbox (Phase 5).
- Any backend changes — the APIs are already built.

## Acceptance criteria
- `npm run typecheck` and `npm run lint` pass with zero errors/warnings.
- Uploading the golden `history.parquet`-derived CSV seed shows a populated
  dashboard with ≥1 forecast point (not cold-start).
- Needs-review transactions display a visible indicator.
- Clicking a category badge and selecting a new one calls `POST /corrections`
  and optimistically updates the badge.
- Cold-start state (< 30 days history) renders a notice, not a broken chart.

## Notes for /plan
Add react-router-dom v6, recharts, and tailwindcss to the frontend. Keep the
existing `api/client.ts` structure — extend it with a `dashboardApi` object.
No SSR, no state management library — local useState + useEffect is sufficient
for this data volume. The corrections endpoint already exists in the backend
(`POST /corrections`).
