# Quickstart: Knowledge & the Agent (Phase 4)

Validation guide proving the agent + RAG work end-to-end. Field shapes are in
[contracts/http-api.md](./contracts/http-api.md) and [contracts/tools.md](./contracts/tools.md);
entities in [data-model.md](./data-model.md).

## Prerequisites

- Phase 1–3 stack up: `docker compose up -d postgres redis minio vault modelserver
  backend worker frontend`.
- Migrations through `0004_agent_rag` applied (`docker compose run --rm migrate` or
  `alembic upgrade head`) — enables the `vector` extension, knowledge tables, and the
  `goals`/`memory` column additions.
- Corpus ingested: `python -m scripts.ingest_corpus` (embeds `rag-corpus/*.md` into
  `knowledge_passages`). Requires an embedding key in Vault, or set `USE_FAKE_LLM` for a
  deterministic local index.
- A seeded account with > 30 days of history, ≥ 1 subscription, and at least one goal.

## Automated gates (stack-independent — these are the CI gates)

```bash
cd backend
ruff check . && mypy .            # lint + type-check
pytest tests/unit -q              # router, agent caps, tools/RLS, RAG, memory audit
pytest tests/test_tool_selection_gate.py -q   # Gate 3 — tool-selection golden set
pytest tests/test_rag_gate.py -q              # Gate 4 — hit@5 / MRR / faithfulness
pytest tests/integration -q       # cross-user isolation (needs Postgres service only)
```

Expected: all green. Gates 3/4 read `tests/golden/**` and `eval_thresholds.yaml`, use
`FakeEmbedder`/a fixed index, and never call a hosted model or start the compose stack
(Art. V).

## Scenario 1 — Enumerable turn answered exactly, off the agent (US1, SC-001, SC-006)

1. POST /chat `{ "message": "What's my balance?" }`.
2. **Expected**: the streamed answer's exact figure equals the balance computed directly
   from the seeded data; final event `route: "deterministic"`; no agent/LLM span in logs.
3. Repeat for "What am I subscribed to?" and "How much did I spend on groceries last
   month?" — all `deterministic`, all exact.

## Scenario 2 — Cited knowledge answer + no-answer gate (US2, SC-004)

1. POST /chat `{ "message": "How big should my emergency fund be?" }`.
2. **Expected**: a grounded answer with ≥ 1 citation (`document_slug` + `heading_path`)
   traceable to a `rag-corpus/` file; no personal figures presented as retrieved facts.
3. POST /chat `{ "message": "What's the capital of France?" }` (off-corpus).
4. **Expected**: a no-answer response admitting it lacks guidance; **no** invented facts
   or citations.

## Scenario 3 — Affordability reconciles all sources (US3, SC-005)

1. POST /chat `{ "message": "Can I afford a £1,200 holiday in August without missing my
   savings goal?" }`.
2. **Expected**: one answer that visibly draws on (a) recent transactions, (b) the
   balance forecast, (c) the savings goal, and (d) cited guidance — `route: "agent"`,
   `citations` non-empty, the personal numbers exact.
3. **Expected**: `bounded: false` in a normal run; the agent used ≤ 8 tool iterations.

## Scenario 4 — Agent stays bounded (SC-008)

1. Drive a deliberately convoluted multi-step prompt (or a test with a forced
   tool-thrash double).
2. **Expected**: the loop stops at ≤ 8 iterations / ~16k tokens and returns a bounded
   best answer (`bounded: true`) — never an infinite loop, never a raw error.

## Scenario 5 — Goals + session memory + durable memory (US4, SC-010)

1. POST /chat `{ "message": "I want to save £5,000 for a car by next June." }`.
   **Expected**: a goal is created (`GET /goals` lists it: name, amount, date, `active`).
2. In the same session, ask "Am I on track for it?" without restating the goal.
   **Expected**: the answer uses the prior turn's context (short-term memory).
3. Ask the agent to "remember that I prefer conservative advice."
   **Expected**: a durable memory is written **and** an `audit_log` row exists for it;
   no durable memory is created by any path other than `write_memory`.
4. Wait past the 30-minute idle window (or expire the session key in a test).
   **Expected**: short-term context is gone; the goal and the durable memory remain.

## Scenario 6 — Conversational writes, validated, scoped, rate-limited (US5, FR-020)

1. "Add a £40 cash payment to the plumber yesterday." **Expected**: the transaction
   appears in the user's data with a category.
2. "That Amazon charge was groceries, not shopping." **Expected**: a correction recorded
   with `human` provenance.
3. Submit a write with a missing field (e.g., no amount). **Expected**: rejected with a
   readable message; no partial write.
4. Fire > 10 writes in a minute. **Expected**: the 11th is throttled with a readable
   message (FR-020).

## Scenario 7 — Cross-user isolation (SC-007, FR-009/024)

1. As user A, ask anything that invokes a tool; as user B, ask the same.
2. **Expected**: no answer ever contains the other user's transactions, goals, or
   memories — verified by `tests/integration/test_chat_isolation.py`.

## Scenario 8 — Rails hook points present but inert (FR-022)

1. Confirm the chat path calls `rails.check_input` / `rails.check_output` /
   `rails.redact`.
2. **Expected**: they are no-ops this phase (behavior unchanged); the call sites exist so
   Phase 6 fills them without re-plumbing.

## Acceptance roll-up

| Spec item | Scenario |
|-----------|----------|
| US1 / SC-001 / SC-006 enumerable exact, off-agent | 1 |
| US2 / SC-004 cited + no-answer | 2 |
| US3 / SC-005 affordability reconciliation | 3 |
| SC-008 bounded agent | 4 |
| US4 / SC-010 goals + memory + audit | 5 |
| US5 / FR-020 writes validated + rate-limited | 6 |
| SC-007 cross-user isolation | 7 |
| FR-022 rails hook points | 8 |
| Gate 3 tool-selection / Gate 4 RAG (SC-002/003) | Automated gates |
