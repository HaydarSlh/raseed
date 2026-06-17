# HTTP API Contract: Knowledge & the Agent (Phase 4)

New endpoints the SPA consumes. All require `Authorization: Bearer <raseed_token>`;
the backend derives `user_id` from the JWT and runs every read/write under the
RLS-scoped session. No endpoint accepts a user id in the body (Art. II).

## POST /chat  *(streamed)*

The single conversational entry point. The backend runs rails input check → router;
enumerable turns are answered deterministically, others go to the bounded agent.

**Request** (JSON):

```jsonc
{
  "message": "Can I afford a £1,200 holiday in August?",
  "session_id": "client-generated-uuid"   // groups turns into one ephemeral session
}
```

**Response**: `200 OK`, streamed (`text/event-stream` or chunked). Tokens stream as
they are produced (FR-002). A terminal event carries structured metadata:

```jsonc
// streamed text chunks: { "delta": "..." }
// final event:
{
  "done": true,
  "route": "agent",                 // "deterministic" | "agent" (FR-005 / SC-006)
  "citations": [
    { "document_slug": "emergency-funds", "heading_path": "Saving > Emergency funds" }
  ],
  "bounded": false                   // true if an agent cap was hit (FR-006)
}
```

**Behavior**:
- Enumerable turn → `route: "deterministic"`, exact figure from SQL, no LLM (SC-001).
- Knowledge answer → `citations` non-empty; empty retrieval → a no-answer message and
  empty `citations` (FR-013/014, SC-004).
- Personal figures always come from exact SQL, never retrieved text (FR-011, SC-007).
- Errors → readable message in the stream; never a stack trace (FR-010, Art. I).
- `401` on missing/expired token → client redirects to `/login`.

## Goals REST

### GET /goals → `200`

```jsonc
[ { "id": "uuid", "name": "Car fund", "target_amount": 5000.0,
    "target_date": "2027-06-01", "status": "active", "created_at": "..." } ]
```

### POST /goals → `201`

```jsonc
// request
{ "name": "Car fund", "target_amount": 5000.0, "target_date": "2027-06-01" }
// response: the created goal (status defaults to "active")
```

- `422` when `name`, `target_amount` (> 0), or `target_date` is missing/invalid (FR-016).

### PATCH /goals/{id} → `200`

```jsonc
// any subset; status transitions active → achieved | abandoned
{ "name": "...", "target_amount": 6000.0, "target_date": "2027-09-01",
  "status": "achieved" }
```

- `404` when the goal id is not the caller's (RLS scoping).
- `422` on invalid status value or non-positive amount.

> The same goal create/update logic backs the `get_goals` / `set_goal` agent tools, so
> chat and REST stay consistent (one service path).

## Notes

- There is **no** endpoint that returns another user's data; RLS + repo scoping enforce
  per-user isolation on every path (FR-024, SC-007).
- Conversations are **not** persisted — there is no `GET /conversations` or transcript
  history endpoint (clarification Q1, ephemeral chat).
- The corpus ingest is an **offline script** (`scripts/ingest_corpus.py`), not an HTTP
  endpoint — it never runs on a request path.
