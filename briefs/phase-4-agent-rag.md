# Phase 4 — Knowledge & the agent

## Intent
A user chats with an agent that answers grounded money questions by combining
exact queries over their own data with cited financial-knowledge retrieval.

## In scope (deliverables)
- RAG: curated openly-licensed corpus in `rag-corpus/` -> heading-aware chunking
  -> hosted-API embeddings -> pgvector (shared corpus, no per-user filter).
  Hybrid (sparse+dense) retrieval; add rerank / query rewriting (Flash-Lite) /
  metadata filtering ONLY where the golden-set number justifies each (record
  the numbers; cut what doesn't pay). Citations on every grounded answer;
  no-answer gate on empty retrieval.
- Deterministic router resolving enumerable turns (balance, subscriptions,
  simple category totals) with exact query + template; ambiguous/multi-step
  turns reach the agent. Log the % of turns kept off the agent.
- Bounded agent (iteration + token caps), explicit allowlist, Pydantic-validated
  inputs, every tool under the caller's RLS context. Tools: query_transactions,
  get_forecast, get_anomalies, get_subscriptions, affordability_check, what_if,
  search_financial_knowledge, get_goals/set_goal, write_memory, add_transaction,
  reclassify_transaction.
- Redis short-term session memory with a justified TTL; goals table CRUD;
  explicit write_memory to user-scoped pgvector with an audit row per write.
- Chat UI with streamed responses.
- RAILS HOOK POINTS: no-op input/output middleware in the chat path and a
  stubbed redaction call site — Phase 6 fills these in (prevents rework).

## Out of scope
Real guardrail logic, red-teaming (Phase 6); review queue & lifecycle (Phase 5).

## Acceptance criteria
- CI gate #3 (tool-selection golden set, ~15 cases) and gate #4 (RAG golden set,
  ~15 triples: hit@5, MRR, faithfulness via RAGAS or frozen judge with reported
  hand-label agreement) green with real numbers.
- The affordability demo genuinely reconciles transactions + forecast + goals
  + RAG in one answer.
- Prompts exist only under `prompts/`.

## Notes for /plan
Flash-Lite for query rewriting/mechanical steps, Flash for synthesis, Grok
failover — all through the Phase-1 adapter. The user's numbers come from exact
SQL, never RAG.
