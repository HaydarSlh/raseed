# Contract: model-server `/healthz` (Phase 0 stub)

The model-server is the lean serving image (onnxruntime + numpy, **no torch** —
Article III). In Phase 0 no model artifact exists and **no refuse-to-boot / SHA-256
guard is enforced** (that guard arrives in Phase 2 with the artifact it guards).

## Endpoint

```
GET /healthz
```

### Response (no model loaded — the Phase 0 steady state)

- **Status**: `200 OK`
- **Body** (shape — exact field names finalized in implementation):

```json
{
  "status": "ok",
  "model": "none",
  "detail": "no model loaded"
}
```

## Behavioral contract

1. **Always healthy without a model**: with no artifact present, `/healthz`
   returns 200 and reports "no model loaded"; the process MUST NOT crash, exit, or
   refuse to boot. *(FR-010, SC-004, spec edge case)*
2. **No hash guard this phase**: the server MUST NOT enforce a SHA-256 match or
   any refuse-to-boot logic in Phase 0. *(Spec out-of-scope; Article III guard
   activates in the phase that introduces the guarded artifact)*
3. **Lean image**: the serving image MUST NOT contain torch or transformers.
   *(Article III)*
4. **Reachable by name**: other services reach it at `http://modelserver:<port>`,
   never localhost. *(FR-004)*
