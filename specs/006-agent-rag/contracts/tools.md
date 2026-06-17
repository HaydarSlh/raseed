# Tool Allowlist Contract: the Bounded Agent (Phase 4)

The **complete, explicit allowlist** (FR-007). The agent can invoke no tool outside
this list. Every tool: (a) has a Pydantic input schema validated before execution
(FR-008); (b) runs under the caller's RLS-scoped session (FR-009, no cross-user
access); (c) on failure returns a structured error the loop can reason about — never a
raw trace (FR-010). Tools return **summaries/aggregates** for LLM context — never raw
rows or identifiers (Art. II). Write tools are additionally rate-limited to 10/min/user
(FR-020) and schema-validated (FR-020/021).

Legend: **Kind** = read \| analysis \| knowledge \| write.

## Read tools (exact SQL — the source of all personal numbers, FR-011)

### query_transactions  *(read)*
- **In**: `{ category?: str, start_date?: date, end_date?: date, limit?: int<=100 }`
- **Out**: `{ count: int, total_amount: float, items: [{date, amount, category}] }`
  (no merchant/description free-text or ids beyond what's needed; aggregates preferred)
- Wraps the transactions repository under RLS.

### get_forecast  *(read)*
- **In**: `{ horizon_days?: int }`
- **Out**: `{ is_cold_start: bool, horizon_days: int, points: [{date, projected_balance}] }`
- DB read of stored derived rows (no Prophet fit on the request path, DESIGN D).

### get_anomalies  *(read)*
- **In**: `{ limit?: int<=50 }`
- **Out**: `{ items: [{anomaly_type, reason}] }`

### get_subscriptions  *(read)*
- **In**: `{}`
- **Out**: `{ items: [{merchant, cadence, typical_amount, next_charge_date, price_increase}] }`

## Analysis tools (compose reads + arithmetic, no new persistence)

### affordability_check  *(analysis)*
- **In**: `{ amount: float>0, when?: date, goal_id?: uuid }`
- **Out**: `{ affordable: bool, projected_balance_at_when: float, goal_impact?: {goal_name, on_track: bool}, rationale: str }`
- Composes `get_forecast` + recent `query_transactions` + (optional) goal; numbers are
  exact (FR-011). The flagship multi-source answer (US3, SC-005).

### what_if  *(analysis)*
- **In**: `{ change: {category?: str, monthly_delta: float} }`
- **Out**: `{ adjusted_projection: [{date, projected_balance}], summary: str }`
- Recomputes a projection under a hypothetical spend change (read-only; no writes).

## Knowledge tool (RAG — never personal numbers, FR-011)

### search_financial_knowledge  *(knowledge)*
- **In**: `{ query: str }`
- **Out**: `{ passages: [{document_slug, heading_path, content}], citations: [...] }`
  or `{ no_answer: true }` when retrieval is empty/below the floor (FR-014, SC-004).
- Hybrid retrieval over the shared corpus (R4); citations always accompany passages
  (FR-013). Returns **no** personal data.

## Goal tools

### get_goals  *(read)*
- **In**: `{ status?: "active"|"achieved"|"abandoned" }`
- **Out**: `{ items: [{id, name, target_amount, target_date, status}] }`

### set_goal  *(write)*
- **In**: `{ id?: uuid, name: str, target_amount: float>0, target_date: date, status?: enum }`
- **Out**: `{ id, name, target_amount, target_date, status }`
- Create (no id) or update (id present); rate-limited; RLS-scoped (FR-016/020).

## Memory tool

### write_memory  *(write)*
- **In**: `{ content: str(1..1024) }`
- **Out**: `{ id, created_at }`
- The **only** durable-memory path (FR-018); embeds + stores user-scoped vector;
  emits one `AuditLog` row (FR-019); rate-limited (FR-020).

## Transaction write tools

### add_transaction  *(write)*
- **In**: `{ txn_date: date, amount: float!=0, description: str(1..1024), merchant?: str, currency?: str="GBP" }`
- **Out**: `{ id, category, confidence, provenance, needs_review }`
- Reuses the Phase-3 ingestion service (in-memory parse/scrub, confidence gate,
  provenance); rate-limited; RLS-scoped.

### reclassify_transaction  *(write)*
- **In**: `{ transaction_id: uuid, new_category: str }`
- **Out**: `{ transaction_id, new_category, provenance: "human" }`
- Writes a `Correction` with `confirmed_by_human=true` and sets provenance `human`
  (Art. III, FR-021); rate-limited; RLS-scoped. (The corrections **review queue** /
  retrain loop is Phase 5 — this only records the human-confirmed correction.)

## Cross-cutting guarantees (asserted by tests)

- **Allowlist closure**: any tool name not above is rejected by the registry (FR-007;
  Gate 3 golden set asserts correct selection).
- **Schema validation**: malformed args are rejected before execution (FR-008;
  `test_tools_rls.py`).
- **RLS isolation**: each tool, invoked as user A, can never read/write user B's data
  (FR-009/024, SC-007; `test_chat_isolation.py`).
- **Structured errors**: a failing tool returns `{ error: <readable> }`, the loop
  continues or apologizes; no stack trace reaches the user (FR-010).
- **Rate limit**: the 11th write in a minute is refused with a readable message
  (FR-020; burst test).
