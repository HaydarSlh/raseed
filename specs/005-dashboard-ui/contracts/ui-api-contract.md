# UI ↔ Backend API Contract: Dashboard UI

The SPA consumes these existing backend endpoints. **No endpoint is added or changed by
this feature.** Shapes below are transcribed from the live backend response models
(`backend/app/api/analytics.py`, `backend/app/api/ingestion.py`,
`backend/app/api/auth.py`) and are the source of truth for `src/api/types.ts`.

All authenticated requests send `Authorization: Bearer <raseed_token>`. The backend
derives `user_id` from the JWT and applies RLS — the SPA never sends a user id.

## Auth (existing, reused)

- `POST /auth/register` — body `{email, password}` → `201`. (Existing `authApi.register`.)
- `POST /auth/jwt/login` — `application/x-www-form-urlencoded` `username,password` →
  `{access_token}`. (Existing `authApi.login`.)
- `GET /users/me` — → current user. (Existing `authApi.me`.)

## GET /dashboard

Auth required. Single aggregate read; all panels come from this one call.

```jsonc
{
  "transactions": [
    { "id": "uuid", "txn_date": "2026-06-01T00:00:00Z", "amount": -12.5,
      "category": "groceries", "confidence": 0.56, "provenance": "model",
      "needs_review": true, "is_anomaly": false }
  ],
  "forecast": {
    "horizon_days": 30,
    "is_cold_start": false,
    "points": [
      { "date": "2026-06-18", "projected_balance": -1501.27,
        "lower": -1600.0, "upper": -1400.0 }
    ]
  },
  "anomalies": [
    { "transaction_id": "uuid", "anomaly_type": "duplicate_charge",
      "reason": "Same merchant and amount within 2 days" }
  ],
  "subscriptions": [
    { "merchant": "Netflix", "cadence": "monthly", "typical_amount": 9.99,
      "next_charge_date": "2026-07-02", "price_increase": false }
  ]
}
```

- Cold-start / no history: `forecast.is_cold_start = true`, `points = []`.
- Brand-new account: `transactions = []` and empty collections → SPA shows empty state.

## GET /forecast

Auth required. Same `forecast` object as above. Used for the manual "Refresh" of the
forecast panel after recompute (R6); the dashboard's primary path uses `/dashboard`.

## GET /subscriptions

Auth required. Returns the `subscriptions[]` array (same item shape as above). Available
as a narrower fetch; the dashboard's primary path uses `/dashboard`.

## POST /uploads

Auth required. **Multipart** `multipart/form-data` with a single field `file` (the CSV).
Do **not** set `Content-Type` manually — let the browser set the boundary. Max 10 MB.

Response `202 Accepted`:

```jsonc
{ "ingested": 5, "needs_review": 4, "duplicates_skipped": 0, "recompute_enqueued": true }
```

Error responses (surface the `detail` string to the user):
- `413` — file too large (> 10 MB).
- `422` — empty file / unparseable / no rows found.

## POST /transactions

Auth required. JSON body (manual single entry):

```jsonc
{ "txn_date": "2026-06-17T00:00:00Z", "amount": -8.99,
  "description": "APPLE MUSIC", "merchant": null, "currency": "GBP" }
```

Response `201 Created`:

```jsonc
{ "id": "uuid", "category": "entertainment", "confidence": 0.74,
  "provenance": "model", "needs_review": false }
```

Error responses:
- `409` — duplicate (matches an existing entry) → readable "already recorded" message.
- `422` — validation (amount is zero, description empty/too long).

## Client surface (to add in `src/api/client.ts`)

```text
dashboardApi.getDashboard()            → GET  /dashboard      → DashboardView
dashboardApi.getForecast()             → GET  /forecast       → ForecastView   (refresh)
dashboardApi.getSubscriptions()        → GET  /subscriptions  → SubscriptionView[]
dashboardApi.uploadStatement(file)     → POST /uploads        → UploadResultView (multipart, bypasses json apiFetch)
dashboardApi.addTransaction(input)     → POST /transactions   → ManualTransactionResultView
```

> Note: there is intentionally **no** `correctCategory` / `POST /corrections` method in
> this phase. The category badge is read-only; the correction action is deferred to the
> ML-lifecycle phase (Phase 5) that owns the corrections store.

## Error handling contract (all calls)

- Non-2xx → throw with the backend `detail` string when present, else `HTTP <status>`.
- The page catching the error shows a readable message and a retry affordance; one
  failing panel never blanks the whole dashboard (FR-013).
- A `401` on a protected page → treat as expired session → redirect to `/login`.
