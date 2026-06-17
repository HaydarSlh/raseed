# HTTP API Contracts — The ML Lifecycle & Ops

All endpoints require a valid JWT. User-scoped endpoints run under the RLS session
(`app.user_id`). Operator endpoints additionally require `is_operator=true` (403
otherwise). Errors return the structured `RaseedError` shape (`{"detail": "..."}`), never
a stack trace.

---

## Review queue & settings (user-scoped)

### `GET /review/queue`
Returns the signed-in user's `needs_review` transactions plus any quarantined LLM
relabels awaiting their confirmation.

Response `200`:
```json
{
  "items": [
    {
      "transaction_id": "uuid",
      "description": "TESCO STORES 1234",
      "merchant": "TESCO",
      "amount": -42.10,
      "occurred_at": "2026-06-10T00:00:00Z",
      "current_category": "groceries",
      "confidence": 0.61,
      "provenance": "model",
      "quarantined": false
    }
  ],
  "review_mode": "manual"
}
```
- `quarantined=true` items are LLM relabels (provenance `llm`) awaiting confirmation.
- Only the owning user's rows appear (RLS). Operators get no special view here.

### `POST /review/confirm`
Confirm or change a flagged row's category. Writes a human-confirmed correction.

Request:
```json
{ "transaction_id": "uuid", "category": "dine_out" }
```
Response `200`: `{ "transaction_id": "uuid", "category": "dine_out", "provenance": "human", "needs_review": false }`
- If the row was a quarantined LLM relabel, this upgrades it: `provenance llm→human`,
  `quarantined→false`, `confirmed_by_human→true` (FR-006).

### `GET /settings/review-mode` → `{ "review_mode": "manual" | "auto_relabel" }`
### `PUT /settings/review-mode`
Request `{ "review_mode": "auto_relabel" }` → `200 { "review_mode": "auto_relabel" }`.
- Switching to `auto_relabel` enqueues a worker job to relabel the user's existing
  flagged rows (provenance `llm`, quarantined). Switching back does NOT retroactively
  un-quarantine already-relabeled rows (edge case).

---

## Ops (operator-only — 403 for non-operators)

### `GET /ops/drift`
Current drift status + recent signal history for charts.
```json
{
  "current": {
    "evaluated_at": "2026-06-17T03:00:00Z",
    "mean_confidence": 0.72, "correction_rate": 0.18,
    "psi": 0.09, "new_merchant_rate": 0.04,
    "fired": false, "fired_signals": [], "triggered_retrain": false
  },
  "thresholds": { "mean_confidence_min": 0.70, "correction_rate_max": 0.20, "psi_max": 0.2, "new_merchant_rate_max": 0.15 },
  "series": [ { "evaluated_at": "...", "mean_confidence": 0.81, "correction_rate": 0.05 } ]
}
```

### `GET /ops/retrains`
Retrain history with champion-vs-challenger numbers.
```json
{
  "runs": [
    {
      "id": "uuid", "trigger_reason": "manual", "status": "completed",
      "champion_macro_f1": 0.8934, "challenger_macro_f1": 0.9012,
      "gate_verdict": "beats", "labels_used": 47,
      "challenger_id": "uuid", "created_at": "...", "completed_at": "..."
    }
  ]
}
```

### `GET /ops/models`
Registry view: current champion + challengers eligible for promotion.
```json
{
  "champion": { "id": "uuid", "version": "v2.1.0", "sha256": "…", "metrics": { "macro_f1": 0.8934 } },
  "promotable": [ { "id": "uuid", "version": "v2.2.0", "sha256": "…", "metrics": { "macro_f1": 0.9012 }, "gate_verdict": "beats" } ]
}
```

### `POST /ops/retrain`
Manually trigger a retrain (operator). Body optional `{ "force": true }` to override the
cooldown (R6).
Response `202`: `{ "retrain_run_id": "uuid", "status": "enqueued" }`
- If a cooldown is active and `force` is not set: `409 { "detail": "retrain cooldown active; pass force=true to override" }`.
- Idempotent: a duplicate trigger in the same window returns the existing run, not a new one.

### `POST /ops/promote`
Promote a challenger (operator-only, HIL). 
Request `{ "model_registry_id": "uuid" }`
Response `200`: `{ "promoted": "uuid", "archived": "uuid", "model_server_reloaded": true }`
- `409` if the challenger's `gate_verdict != 'beats'` (cannot promote a non-winner, FR-015).
- `403` for non-operators (FR-016).
- On model-server reload SHA mismatch: `502 { "detail": "model-server reload failed (hash mismatch); champion unchanged" }` and the registry swap is rolled back (FR-017).

---

## Model-server (internal, backend→model-server)

### `POST /reload`  (model-server)
Request `{ "sha256": "…" }` — re-resolve artifact by SHA via the MinIO provider,
re-verify SHA, atomically swap the loaded categorizer.
Response `200`: `{ "status": "reloaded", "sha256": "…" }`
Failure `409`: `{ "detail": "sha256 mismatch — reload refused, prior model retained" }`
(prior categorizer kept; never serves a mismatched model).

The caller (backend promote path) supplies the authoritative SHA; the server verifies
it and downloads-by-that-SHA, never selecting a model on its own (single source of
truth = the promoting backend; R3/C2).
