# HTTP API Contract — Ingestion & Analytics

All endpoints require a valid JWT; `user_id` is derived from the token, never the body
(constitution Art. II). Routers are thin (`api/` → `services/`), never touching SQL. Errors
map to the domain exception hierarchy → structured JSON (no stack traces).

## POST /uploads — upload a statement

- **Request**: `multipart/form-data` with one file field (`file`), a delimited CSV-class
  statement export.
- **Behavior**: parse in memory → scrub PAN/IBAN → `ingest_transactions` → enqueue recompute.
  Raw bytes are never persisted.
- **Response 202**:
  ```json
  { "ingested": 42, "needs_review": 5, "duplicates_skipped": 3, "recompute_enqueued": true }
  ```
- **Errors**: `422` malformed/unsupported file (nothing stored); `413` too large.

## POST /transactions — add one transaction manually

- **Request**:
  ```json
  { "txn_date": "2026-06-10", "amount": -12.50, "description": "CASH LUNCH" }
  ```
- **Behavior**: same `ingest_transactions` path as upload (one row) → enqueue recompute.
- **Response 201**:
  ```json
  { "id": "…", "category": "dine_out", "confidence": 0.93, "provenance": "model", "needs_review": false }
  ```
- **Errors**: `422` invalid amount (zero) / bad date.

## GET /dashboard — aggregated dashboard payload (DB read only)

- **Response 200**:
  ```json
  {
    "transactions": [ { "id":"…","txn_date":"…","amount":-12.5,"category":"dine_out",
                        "confidence":0.93,"provenance":"model","needs_review":false,"is_anomaly":false } ],
    "forecast": { "horizon_days":30, "is_cold_start":false,
                  "points":[ {"date":"…","projected_balance":1234.5,"lower":1100.0,"upper":1360.0} ] },
    "anomalies": [ { "transaction_id":"…","anomaly_type":"statistical_outlier","reason":"…" } ],
    "subscriptions": [ { "merchant":"…","cadence":"monthly","typical_amount":9.99,
                         "next_charge_date":"…","price_increase":false } ]
  }
  ```
- **Behavior**: pure DB reads of stored derived rows; independent reads fan out via
  `asyncio.gather`. No model-server call, no Prophet fit on this path.

## GET /forecast · /anomalies · /subscriptions

- Narrow DB-read endpoints returning the matching slice of the `/dashboard` payload, for the
  agent tools in Phase 4 and for partial UI refresh. Each is a stored-data read (Art. V).

## Isolation contract

- Every endpoint operates strictly within the caller's RLS context; no endpoint accepts or
  honors a `user_id` from the request. A cross-user read returns the caller's empty/own data,
  never another user's rows.
