# Data Model: Security & Compliance Hardening

## New Entities

### ErasureAudit

Operator-only audit record produced by every right-to-erasure request.

| Field | Type | Constraints |
|-------|------|-------------|
| `id` | UUID | PK, auto-generated |
| `user_id` | UUID | NOT NULL; the requesting user's ID (retained after user is deleted) |
| `requested_at` | TIMESTAMPTZ | NOT NULL, server default NOW() |
| `completed_at` | TIMESTAMPTZ | NULL until purge finishes; set in the same write that records per-store counts |
| `per_store_counts` | JSONB | NOT NULL; e.g. `{"transactions": 47, "corrections": 3, ...}` |
| `status` | TEXT | NOT NULL; `pending | completed | failed`; enum-validated |

**RLS policy**: NONE — this table is NOT subject to `app.user_id` row-level
security. It is readable only by operators (privileged DB role or is_operator=True
users). It is NOT purged when the referenced user is erased.

**Migration**: Added in `0006_security_hardening.py`.

---

## In-Process Entities (not persisted)

### RailDecision

Result of evaluating `check_input` or `check_output` against a message. Lives
only for the duration of a single request — never written to any store.

| Field | Type | Description |
|-------|------|-------------|
| `action` | `"pass" \| "block"` | Whether the message is forwarded or refused |
| `trigger_reason` | `str \| None` | Category: `injection`, `jailbreak`, `extraction`, `off_domain`, `advice`, `pii` |
| `user_facing_message` | `str \| None` | Plain-language refusal shown to the user when `action == "block"` |

Raised as a `RailRefusal` exception (subclass of `RaseedError`) when
`action == "block"`, caught at the `chat.py` streaming generator boundary.

### RedactionRecord

In-process transform result produced by `redact()`. Never persisted or logged.

| Field | Type | Description |
|-------|------|-------------|
| `original` | `str` | Raw input text (never forwarded after redaction runs) |
| `redacted` | `str` | Text with PII patterns replaced by `[REDACTED-*]` tokens |
| `patterns_matched` | `list[str]` | Pattern names that fired (e.g. `["CARD", "EMAIL"]`) |

The `redacted` field is the only value passed to the LLM or logs. The `original`
field is never stored.

---

## Existing Entities Affected

### User (`users` table)

No schema change. The erasure service hard-deletes this row last (after all
FK-referencing tables are cleared). fastapi-users' `is_active=False` soft-delete
is NOT used — erasure is a hard delete.

### Memory (`memory` table)

Contains pgvector embedding column. The erasure service deletes all rows
`WHERE user_id = ?` — this removes the pgvector data for that user without
requiring a separate vector-store call, because the embeddings are stored inline
in the Postgres table (not an external vector DB).

---

## Erasure Purge Order (FK-safe)

```
1. corrections       (FK → transactions: SET NULL already, FK → users: CASCADE)
2. memory            (FK → users: CASCADE implied; explicit DELETE for clarity)
3. user_settings     (FK → users: CASCADE)
4. goals             (FK → users: CASCADE)
5. forecasts         (FK → users: CASCADE)
6. anomalies         (FK → users: CASCADE)
7. subscriptions     (FK → users: CASCADE)
8. transactions      (FK → users: CASCADE)
9. users             (the user row itself)
```

After the Postgres transaction commits:
- Redis: SCAN + DEL all keys matching `raseed:*:{user_id}` and any
  fastapi-users session keys for the user.
- `erasure_audit` row: written in a separate, subsequent transaction with
  `completed_at` and `per_store_counts`.
