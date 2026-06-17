# API Contract: Right-to-Erasure

## DELETE /users/me/erasure

Permanently deletes all data owned by the authenticated user across every
persistent store. Returns immediately with 202 Accepted; the purge runs
synchronously before the response is sent (user count is small, p95 < 500 ms).

### Request

```
DELETE /users/me/erasure
Authorization: Bearer <JWT>
Content-Type: application/json
```

No request body required. Authentication via the standard JWT bearer token.

### Response: 202 Accepted

```json
{
  "audit_id": "uuid",
  "status": "completed",
  "deleted_counts": {
    "corrections": 3,
    "memory": 12,
    "user_settings": 1,
    "goals": 2,
    "forecasts": 6,
    "anomalies": 1,
    "subscriptions": 4,
    "transactions": 47
  },
  "message": "All your data has been permanently deleted. This action cannot be undone."
}
```

### Response: 401 Unauthorized

No valid JWT provided (standard FastAPI/fastapi-users response).

### Response: 500 Internal Server Error

Purge failed partway through. The `erasure_audit` row is written with
`status = "failed"` and `completed_at = null`. The user should retry; partial
deletes are idempotent (deleting already-deleted rows is a no-op).

### Behaviour invariants

1. The user's own `users` row is deleted last. After this, subsequent API calls
   with the same JWT return 401 (token valid but user not found).
2. The session is invalidated as part of the erasure (Redis session keys deleted).
3. The `erasure_audit` record is written with `status = "completed"` only after
   all stores confirm zero rows for the user.
4. The audit record is retained even after the user row is deleted — it is NOT
   subject to user-scoped RLS.
5. If a retrain job is running that references this user's corrections, the
   corrections DB rows are still deleted; the in-memory training batch already
   loaded into the trainer is not affected (documented limitation in SECURITY.md).

---

## Rail Refusal Contract (input/output rails)

When `check_input` or `check_output` fires, the chat streaming endpoint yields
a single event and closes the stream:

```json
{"error": "refusal", "reason": "<plain-language explanation>", "rail": "input|output"}
```

HTTP status remains 200 (the StreamingResponse is already open). The frontend
must inspect the event for the `error` key to detect refusals.

**Refusal reasons by category**:

| Category | User-facing message |
|----------|---------------------|
| `injection` | "I can't process messages that attempt to override my instructions." |
| `jailbreak` | "I can only assist with personal finance questions in my designed role." |
| `extraction` | "I'm not able to reveal information about my configuration." |
| `off_domain` | "I'm a personal-finance assistant. I can only help with questions about your finances." |
| `advice` | "I can share financial information but cannot provide personalised investment or legal advice. Please consult a qualified professional." |

The `original` message is never included in any log line or response field.
