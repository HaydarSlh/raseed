# Contract: model-server `/predict` and `/healthz` (Phase 2)

The lean model-server (onnxruntime + numpy + `tokenizers`, **no torch** — Art. III)
now serves a real model. Reachable as `http://modelserver:8080` (never localhost).

## `POST /predict`

### Request
```json
{ "description": "STARBUCKS STORE #1234 SEATTLE WA", "top_k": 3 }
```
- `description`: required string, trimmed length 1..512, not whitespace-only.
- `top_k`: optional int, default 3, range 1..5.

### Response — 200 OK
```json
{
  "category": "dining",
  "confidence": 0.94,
  "alternatives": [
    { "category": "dining", "score": 0.94 },
    { "category": "groceries", "score": 0.03 },
    { "category": "shopping", "score": 0.01 }
  ],
  "low_confidence": false
}
```

### Behavioral contract
1. **Closed-set output**: `category` and every `alternatives[].category` MUST be
   members of the locked taxonomy. *(FR-001, FR-011)*
2. **Calibrated confidence**: `confidence` ∈ [0,1] and is calibrated (R4). *(FR-008)*
3. **Ranked alternatives**: `alternatives` is descending by `score`, length ≤
   `top_k`, and **includes the primary category at rank 0** (single canonical shape).
   *(FR-011)*
4. **Per-category low-confidence flag**: `low_confidence` is true iff `confidence`
   is below the predicted category's operating threshold, or that category is a
   `always_review` sentinel. The service still returns its best category. *(FR-009,
   FR-010)*
5. **Validation errors are structured**: empty/whitespace/oversized `description`
   or out-of-range `top_k` → HTTP 422 structured error, never a stack trace.
   *(FR-017)*
6. **Latency**: p95 single-call < 200 ms on CPU. *(SC-001)*
7. **Stateless**: no `user_id`, no persistence, no logging of the raw description at
   info level (description may carry merchant PII; log only metadata + category).
   *(Art. II)*

## `GET /healthz`

### Response — 200 OK (model loaded & verified)
```json
{ "status": "ok", "model": "loaded", "sha256": "<pinned>", "taxonomy_version": "1" }
```

### Behavioral contract
1. **Ready only with a verified model**: reports ready **only** while an artifact is
   loaded AND its SHA-256 matched the pinned value. *(FR-012, FR-013)*
2. If no verified model is loaded the process is **not ready** — see
   `model-artifact.md` (refuse-to-boot); `/healthz` does not report a happy "ok"
   over a missing/mismatched model (this supersedes the Phase 0 "no model loaded"
   steady state). *(FR-013)*

## Observability
- structlog JSON with a request ID per call; a span per prediction carrying latency
  (and, for the zero-shot eval path only, token/cost — not in the serving path).
  *(Art. V)*
