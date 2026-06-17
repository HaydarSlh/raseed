# Implementation Plan: Knowledge & the Agent

**Branch**: `006-agent-rag` | **Date**: 2026-06-17 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/006-agent-rag/spec.md`

## Summary

Add a chat surface where a signed-in user asks money questions and gets grounded
answers. A **deterministic router** resolves enumerable turns (balance,
subscriptions, simple category totals) with exact SQL + a template, keeping them
off the LLM. Ambiguous/multi-step turns reach a **bounded tool-calling agent**
(≤ 8 iterations, ~16k-token budget) that selects from an explicit, Pydantic-validated,
RLS-scoped tool allowlist. **RAG** over a shared, openly-licensed financial-literacy
corpus answers knowledge questions with citations and a no-answer gate; personal
numbers always come from exact SQL, never RAG. Goals get full CRUD; short-term
session memory lives in Redis with a 30-minute idle TTL; durable memory is written
only via an audited `write_memory` into user-scoped pgvector. No-op rails hook points
(input/output checks + a redaction call site) ship in the chat path for Phase 6 to
fill. All hosted-model calls route through the existing Phase-1 LLM adapter
(Flash-Lite mechanical / Flash synthesis / Grok failover).

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5.4 / React 18.3 (frontend).

**Primary Dependencies**: Existing — FastAPI (async, layered), async SQLAlchemy,
Postgres + pgvector, Redis (RQ + sessions), the Phase-1 LLM adapter (`infra/llm.py`),
structlog, tenacity (`with_retry`). Added — `pgvector` Python bindings + the `vector`
Postgres extension (dense retrieval), Postgres native full-text search (`tsvector`/
`ts_rank`) for the sparse side (no new dependency), a hosted embedding model via the
LLM adapter boundary. Frontend — existing React Router v6 + Tailwind + the streaming
`fetch` reader; no new runtime libs required.

**Storage**: Postgres — new `knowledge_documents` + `knowledge_passages` (shared
corpus, dense `vector(768)` + `tsvector`), `goals` (extend: required fields + status),
`memory` (add `vector(768)` embedding), `audit_log` (exists). Redis — short-term
conversation context (30-min idle TTL) and the per-user write rate-limit counter.
MinIO untouched (model artifacts only). Raw corpus files live in `rag-corpus/` at the
repo root and are embedded by an offline ingest script — never user data.

**Testing**: pytest (unit + integration, `FakeLLM`/`FakeEmbedder` doubles so CI never
calls a hosted model or starts the stack), plus two committed golden-set gates —
tool-selection (~15 cases) and RAG (~15 triples: hit@5, MRR, faithfulness). Frontend:
Vitest + React Testing Library.

**Target Platform**: Linux server (Docker Compose); modern desktop browsers for the SPA.

**Project Type**: Web application — FastAPI backend + React SPA, consuming the existing
Phase 1–3 services.

**Performance Goals**: Streamed first token perceived promptly (qualitative, SC-009 —
a hard latency budget is future work per PLAN). The deterministic router answers
enumerable turns without an LLM call. RAG retrieval and embedding calls use TTL caches
(Art. V); transaction-derived reads remain invalidate-on-write.

**Constraints**: Agent bounded at ≤ 8 tool iterations and ~16k tokens/turn (FR-006);
every tool input Pydantic-validated and executed under the caller's RLS session
(`app.user_id`); personal figures from exact SQL only (FR-011); citations on every
grounded knowledge answer + no-answer on empty retrieval (FR-013/014); agent writes
rate-limited to 10/min/user (FR-020); prompts only under `backend/prompts/` (FR-023);
no identifiers cross the LLM boundary — only summaries/aggregates (Art. II); users
never see a stack trace (Art. I).

**Scale/Scope**: Single-user data volumes (tens–hundreds of transactions); corpus on
the order of dozens of documents → low thousands of passages. 12 agent tools, 1
deterministic router, 1 hybrid retriever, 1 chat page + a handful of components.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Art. I — Layered, Async Architecture**: New code is layered — `api/chat.py` +
  `api/goals.py` (HTTP only) → `services/agent/*` and `services/rag/*` (logic) →
  `repositories/*` (SQL) → `domain/*` (Pydantic/ORM); `infra/` holds the embedding
  client and the reused LLM adapter. Every LLM/DB/retrieval call is awaited; the agent
  fans out independent reads via `asyncio.gather`. The LLM adapter, embedder, and
  retriever are lifespan singletons injected with `Depends`. Errors map through the
  existing `RaseedError` hierarchy — no stack traces to users. **PASS**
- **Art. II — Isolation & Data Protection (NON-NEGOTIABLE)**: Every tool runs under the
  request's RLS-scoped session (`get_rls_session`, `app.user_id`); memory and goals are
  user-scoped and RLS-enforced. The knowledge corpus is deliberately shared and carries
  no user data, so it is not user-filtered (consistent with Art. IV "RAG serves only
  the shared corpus"). Only summaries/aggregates are placed in LLM context — never
  identifiers or raw rows; a redaction call site sits before every egress (no-op this
  phase). Webhooks/logs unaffected. **PASS**
- **Art. III — ML Lifecycle Integrity**: `reclassify_transaction` writes a correction
  with `human` provenance (`confirmed_by_human=true`) — it does not train anything here;
  the retrain gate stays in Phase 5. No torch/transformers enter any serving image; the
  embedder is a hosted API behind the adapter, not a local heavy model. **PASS**
- **Art. IV — Bounded Agent & Grounded RAG**: This phase *is* Art. IV. One bounded loop
  (8 iters / 16k tokens) behind a deterministic router; explicit tool allowlist;
  Pydantic-validated inputs; every tool RLS-scoped; LLM-triggered writes
  (`add_transaction`, `set_goal`, `reclassify_transaction`, `write_memory`)
  schema-validated, rate-limited, user-scoped; numbers from exact SQL, never RAG;
  citations always + no-answer on empty retrieval; `write_memory` is the only
  durable-memory path and every write is audit-logged; retrieval is user-filtered for
  memory and shared for the corpus; prompts live as files under `backend/prompts/`.
  **PASS**
- **Art. V — Quality & Operations**: Every hosted call goes through the adapter's
  timeout + tenacity backoff with Gemini→Grok failover; 4xx not retried; tool failures
  return structured errors. `lru_cache` for deterministic work, TTL caches for RAG
  retrieval + embedding calls; transaction-derived reads stay invalidate-on-write.
  structlog spans per LLM/tool/retrieval call carry token/cost fields. Gates #3
  (tool-selection) and #4 (RAG) land in `eval_thresholds.yaml` with real numbers and
  block regressions; golden sets are committed so CI never touches the running stack or
  a hosted model (FakeLLM/FakeEmbedder). Secrets (Gemini/Grok keys, embedding key)
  resolve from Vault; nothing hardcoded. Every tuned number is recorded in
  `DECISIONS.md`. **PASS**

**Stack compliance**: Postgres+pgvector, Redis, the fixed LLM adapter, and the React
SPA are all the mandated stack. pgvector dense + Postgres full-text sparse are features
of the existing data store, not new infrastructure. **PASS** — no Complexity Tracking
entries required.

## Project Structure

### Documentation (this feature)

```text
specs/006-agent-rag/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── http-api.md      # /chat (stream), /goals CRUD wire shapes
│   └── tools.md         # the 12-tool allowlist: input/output schemas + RLS/limits
└── tasks.md             # Phase 2 output (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
rag-corpus/                              # NEW — curated openly-licensed source docs (markdown)
└── *.md                                 # CFPB/MoneyHelper-class + own explainers (+ SOURCES.md license note)

backend/
├── prompts/                             # NEW — all prompts as files (FR-023)
│   ├── agent_system.txt                 # bounded-agent system prompt + tool protocol
│   ├── synthesis.txt                    # grounded-answer synthesis (citations, no-answer)
│   ├── query_rewrite.txt                # Flash-Lite retrieval query rewrite (gated by R-num)
│   └── no_answer.txt                    # empty-retrieval no-answer template
├── app/
│   ├── api/
│   │   ├── chat.py                      # NEW — POST /chat (streamed), router→agent entry
│   │   └── goals.py                     # NEW — goals CRUD REST
│   ├── services/
│   │   ├── agent/                       # NEW package
│   │   │   ├── router.py                # deterministic enumerable-turn classifier + templates
│   │   │   ├── loop.py                  # bounded ReAct loop (caps, allowlist dispatch)
│   │   │   ├── rails.py                 # no-op input/output checks + redaction call site
│   │   │   ├── ratelimit.py             # per-user write rate limiter (Redis, 10/min)
│   │   │   └── tools/                   # allowlisted tools, one concern per file
│   │   │       ├── registry.py          # allowlist + Pydantic IO schema binding
│   │   │       ├── reads.py             # query_transactions, get_forecast, get_anomalies, get_subscriptions
│   │   │       ├── analysis.py          # affordability_check, what_if
│   │   │       ├── knowledge.py         # search_financial_knowledge (RAG)
│   │   │       ├── goals.py             # get_goals, set_goal
│   │   │       ├── memory.py            # write_memory (audited)
│   │   │       └── writes.py            # add_transaction, reclassify_transaction
│   │   ├── rag/                         # NEW package
│   │   │   ├── chunking.py              # heading-aware chunker
│   │   │   ├── retrieval.py             # hybrid dense+sparse fusion, no-answer gate
│   │   │   └── ingest.py                # offline corpus → embeddings → pgvector (script entry)
│   │   └── session_memory.py            # NEW — Redis short-term context (30-min TTL)
│   ├── repositories/
│   │   ├── goals_repo.py                # NEW
│   │   ├── memory_repo.py               # NEW — user-scoped vector upsert + query
│   │   └── knowledge_repo.py            # NEW — shared corpus dense+sparse query
│   ├── infra/
│   │   ├── llm.py                       # REUSE — tool-loop uses existing complete() (no change)
│   │   └── embeddings.py               # NEW — hosted embedder (768-dim) + FakeEmbedder (the embed() home)
│   ├── domain/
│   │   ├── goal.py                      # EXTEND — required fields + status enum
│   │   ├── memory.py                    # EXTEND — vector(768) embedding column
│   │   └── knowledge.py                 # NEW — KnowledgeDocument, KnowledgePassage
│   ├── schemas/
│   │   ├── chat.py                      # NEW — chat request/response, router decision
│   │   └── goal.py                      # NEW — goal create/update/out
│   └── alembic/versions/
│       └── 0004_agent_rag.py            # NEW — vector ext, knowledge tables, goal+memory cols
├── scripts/
│   └── ingest_corpus.py                 # NEW — CLI wrapper over services/rag/ingest.py
└── tests/
    ├── golden/
    │   ├── tool_selection/cases.yaml    # NEW — ~15 turn→expected-route/tool cases (Gate 3)
    │   └── rag/triples.yaml             # NEW — ~15 question/passage/answer triples (Gate 4)
    ├── test_router.py                   # unit — enumerable routing + % off-agent
    ├── test_agent_loop.py               # unit — caps, allowlist, structured tool errors
    ├── test_tools_rls.py               # unit — every tool RLS-scoped + Pydantic-validated
    ├── test_rag_retrieval.py            # unit — hybrid + no-answer gate + citations
    ├── test_memory_audit.py             # unit — write_memory audited + user-filtered
    ├── test_tool_selection_gate.py      # Gate 3 — reads cases.yaml + eval_thresholds
    ├── test_rag_gate.py                 # Gate 4 — hit@5/MRR/faithfulness vs thresholds
    └── integration/
        └── test_chat_isolation.py       # cross-user: no tool leaks another user's data

frontend/
└── src/
    ├── pages/Chat.tsx                   # NEW — streamed chat page
    ├── components/
    │   ├── ChatMessage.tsx              # NEW — message bubble + citations render
    │   └── ChatInput.tsx                # NEW — prompt box, send, streaming state
    ├── api/chatApi.ts                   # NEW — POST /chat stream reader, goals client
    └── components/NavBar.tsx            # EXTEND — add Chat link
```

**Structure Decision**: Web application. Backend work lands in two new service
packages (`services/agent/`, `services/rag/`) plus thin `api/` routers, new
repositories, three domain extensions/additions, one Alembic migration, a prompts
folder, and two committed golden sets. The frontend adds one routed Chat page and a
streaming client. All tools wrap existing Phase 1–3 services/repositories rather than
reimplementing logic; the corpus lives at the repo root in `rag-corpus/` and is
embedded by an offline script — never user data.

## Complexity Tracking

> No constitution violations. No entries required.
