# Data Model: Knowledge & the Agent (Phase 4)

New and extended persistent entities, plus the transient/session shapes. Field names
match the planned ORM/Pydantic models. Migration: `0004_agent_rag.py` (enables the
`vector` extension, adds the knowledge tables, and extends `goals` + `memory`).

## Persistent (Postgres)

### KnowledgeDocument  *(new — shared, no user_id)*

A source in the curated financial-literacy library.

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID (PK) | |
| `slug` | text, unique | Stable id from filename, used in citations. |
| `title` | text | Document title (from first heading). |
| `source` | text | Origin/publisher (e.g., "CFPB", "MoneyHelper", "Raseed"). |
| `license` | text | License identifier; mirrors `rag-corpus/SOURCES.md`. |
| `content_hash` | text | Hash of the source file; ingest idempotency. |
| `created_at` | timestamptz | |

**Not user-scoped** — shared corpus, no RLS policy (carries no user data; Art. IV
allows the shared knowledge corpus to be unfiltered).

### KnowledgePassage  *(new — shared, no user_id)*

A heading-aware chunk of a document; the unit of retrieval and citation.

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID (PK) | |
| `document_id` | UUID (FK → knowledge_documents, CASCADE) | |
| `heading_path` | text | e.g., "Saving > Emergency funds"; the citation label. |
| `ordinal` | int | Passage order within the document. |
| `content` | text | Passage text. |
| `content_hash` | text | Per-passage hash; idempotent re-ingest. |
| `embedding` | `vector(768)` | Dense vector (R3). IVFFlat/HNSW cosine index. |
| `tsv` | `tsvector` | Generated from `content`; GIN index (sparse side, R4). |

**Display/retrieval rules**: dense cosine top-k ∪ sparse `ts_rank` top-k → RRF (R4);
shared across users; a citation references `(document.slug, heading_path)`.

### Goal  *(extend existing `goals`)*

| Field | Type | Change |
|-------|------|--------|
| `id` | UUID (PK) | existing |
| `user_id` | UUID (FK → users, CASCADE) | existing; RLS-scoped |
| `name` | text | existing; **now required** (already non-null) |
| `target_amount` | Numeric(18,4) | **now required** (was nullable) — clarification Q5 |
| `target_date` | date | **now required** (was nullable) — clarification Q5 |
| `status` | text enum | **new** — `active` \| `achieved` \| `abandoned`, default `active` |
| `created_at` | timestamptz | existing |
| `updated_at` | timestamptz | **new** — set on status/field updates |

**Validation**: `target_amount > 0`; `status` constrained to the three values.
**State transitions**: `active → achieved`, `active → abandoned` (terminal); a goal is
never hard-deleted by the agent (status change instead).

### Memory  *(extend existing `memory`)*

| Field | Type | Change |
|-------|------|--------|
| `id` | UUID (PK) | existing |
| `user_id` | UUID (FK → users, CASCADE) | existing; RLS-scoped |
| `content` | text | existing |
| `embedding` | `vector(768)` | **new** — dense vector for user-filtered recall (R3) |
| `created_at` | timestamptz | existing |

**Write rule**: created **only** via the `write_memory` tool (FR-018); every write
emits an `AuditLog` row (FR-019). Retrieval is **user-filtered** by RLS (never shared).

### AuditLog  *(existing — reused, no schema change)*

`write_memory` (and other agent writes worth auditing) append `action` +
`detail` (JSONB) rows. One row per durable-memory write (FR-019).

### Correction  *(existing — reused by `reclassify_transaction`)*

Agent reclassification writes a correction with `confirmed_by_human=true` and drives
the transaction's provenance to `human` (Art. III, FR-021). No schema change.

## Transient (Redis)

### SessionContext  *(new — Redis, not Postgres)*

Rolling short-term conversation context for an active chat session.

| Aspect | Value |
|--------|-------|
| Key | per session (derived from user + session id) |
| Value | ordered recent turns (user text + assistant answer, trimmed to budget) |
| TTL | **30-minute sliding/idle** TTL, refreshed each turn (R6, FR-017) |
| Lifetime | ephemeral — never persisted; expires on inactivity (clarification Q1) |

### WriteRateCounter  *(new — Redis)*

| Aspect | Value |
|--------|-------|
| Key | `user_id` + current-minute window |
| Value | integer count of agent writes this window |
| Limit | 10/min/user → 11th refused (R7, FR-020) |

## In-process (Pydantic, not persisted)

### RouterDecision

| Field | Type | Notes |
|-------|------|-------|
| `route` | enum | `deterministic` \| `agent` |
| `intent` | str \| null | enumerable intent when deterministic (balance/subscriptions/category_total) |
| `turn_id` | str | correlates with the logged span; feeds the % off-agent metric (FR-005) |

### ToolCall / ToolResult

| Field | Type | Notes |
|-------|------|-------|
| `tool` | str | must be in the allowlist (FR-007) |
| `args` | validated model | per-tool Pydantic input schema (FR-008) |
| `result` | model \| StructuredError | structured error on failure — never a raw trace (FR-010) |

### AgentAnswer

| Field | Type | Notes |
|-------|------|-------|
| `text` | str | streamed to the client (FR-002) |
| `citations` | list[Citation] | present for any knowledge-grounded answer (FR-013); empty for pure-data answers |
| `bounded` | bool | true if a cap was hit (FR-006) |

### Citation

| Field | Type | Notes |
|-------|------|-------|
| `document_slug` | str | → KnowledgeDocument.slug |
| `heading_path` | str | → KnowledgePassage.heading_path |

## Relationships

- `KnowledgeDocument 1—* KnowledgePassage` (shared corpus; no user link).
- `User 1—* Goal`, `User 1—* Memory`, `User 1—* AuditLog`, `User 1—* Correction`
  (all RLS-scoped on `app.user_id`).
- `Citation` references a `KnowledgePassage` by `(document_slug, heading_path)`.
- `Correction` references a `Transaction` (existing) and drives its provenance.
- `SessionContext` and `WriteRateCounter` are Redis-only and reference a user logically,
  not by FK.
