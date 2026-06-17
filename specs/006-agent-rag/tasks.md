---
description: "Task list for Knowledge & the Agent (Phase 4)"
---

# Tasks: Knowledge & the Agent

**Input**: Design documents from `specs/006-agent-rag/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/http-api.md,
contracts/tools.md, quickstart.md

**Tests**: INCLUDED — the constitution (Art. V) requires every phase to ship tests, and
the brief makes CI gate #3 (tool-selection) and gate #4 (RAG) acceptance criteria. All
tests use `FakeLLM`/`FakeEmbedder` and committed golden sets so CI never calls a hosted
model or starts the compose stack.

**Organization**: Tasks are grouped by user story. Backend paths are under `backend/`;
frontend under `frontend/`; corpus at the repo-root `rag-corpus/`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no incomplete dependencies)
- **[Story]**: US1–US5 maps to the spec's user stories

---

## Phase 1: Setup (Shared Infrastructure)

- [X] T001 Add the dense-vector dependency and tunables: add `pgvector` to
  `backend/pyproject.toml`, and add to `backend/app/core/config.py` (Settings):
  `embedding_model`, `embedding_dim: int = 768`, `agent_max_iterations: int = 8`,
  `agent_token_budget: int = 16000`, `session_ttl_seconds: int = 1800`,
  `write_rate_per_min: int = 10`. The embedder reuses the existing `gemini_api_key`
  (no separate embedding key) — record this in DECISIONS (T047).
- [X] T002 [P] Create the corpus folder `rag-corpus/` with `SOURCES.md` (a license table)
  and an initial set of openly-licensed financial-literacy markdown docs (e.g.
  emergency-funds, apr-vs-apy, budgeting-basics, paying-down-debt, building-savings),
  each with clear headings for heading-aware chunking.
- [X] T003 [P] Create the prompt files under `backend/prompts/`: `agent_system.txt`
  (bounded-agent system prompt + JSON-action tool protocol), `synthesis.txt`
  (grounded-answer synthesis with citation + no-answer rules), `query_rewrite.txt`
  (Flash-Lite retrieval rewrite), and `no_answer.txt` (empty-retrieval template).

**Checkpoint**: deps install; settings load; corpus + prompts exist as files.

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T004 Extend `backend/app/domain/goal.py`: make `target_amount` and `target_date`
  NOT NULL, add `status` (enum `active`/`achieved`/`abandoned`, default `active`) and
  `updated_at` (data-model Goal).
- [X] T005 [P] Extend `backend/app/domain/memory.py`: add `embedding` `Vector(768)` column.
- [X] T006 [P] Create `backend/app/domain/knowledge.py`: `KnowledgeDocument` (slug, title,
  source, license, content_hash) and `KnowledgePassage` (document_id FK, heading_path,
  ordinal, content, content_hash, `embedding Vector(768)`, `tsv` tsvector) — shared, no
  user_id (data-model).
- [X] T007 Create migration `backend/alembic/versions/0004_agent_rag.py`: `CREATE
  EXTENSION IF NOT EXISTS vector`; create `knowledge_documents` + `knowledge_passages`
  (ivfflat cosine index on `embedding`, GIN index on `tsv`); alter `goals`
  (NOT NULL on amount/date, add `status` + `updated_at`); add `memory.embedding`. No RLS
  policy on the knowledge tables (shared corpus); goals/memory keep their RLS policies.
  (Depends on T004–T006.)
- [X] T008 [P] Create `backend/app/infra/embeddings.py`: a hosted Gemini embedder
  (768-dim, reusing `gemini_api_key`) behind a `BaseEmbedder` interface, a deterministic
  `FakeEmbedder` (hash→seeded vector) for CI/local, a TTL cache on embed calls, and
  `init_embedder`/`get_embedder` singletons (research R3, Art. V). This module is the
  sole home of `embed()`; `infra/llm.py` is reused unchanged for the tool-loop.
- [X] T009 [P] Create `backend/app/schemas/chat.py` (`ChatRequest`, streamed delta + final
  event models, `RouterDecision`) and `backend/app/schemas/goal.py` (`GoalCreate`,
  `GoalUpdate`, `GoalOut`) per contracts.
- [X] T010 [P] Create `backend/app/services/agent/rails.py`: no-op `check_input`,
  `check_output`, and `redact` returning their input unchanged (FR-022).
- [X] T011 [P] Create `backend/app/services/agent/ratelimit.py`: a Redis fixed-window
  per-user counter enforcing `write_rate_per_min` (10/min), raising a readable
  domain error on the 11th write in a window (FR-020, research R7).
- [X] T012 [P] Create `backend/app/services/session_memory.py`: Redis-backed rolling
  conversation context keyed by session, with a 30-minute sliding TTL refreshed each
  turn (FR-017, research R6).
- [X] T013 Create `backend/app/services/agent/tools/registry.py`: the explicit allowlist,
  per-tool Pydantic input-schema binding, and a dispatch function that rejects any
  non-allowlisted tool name and validates args before execution (FR-007/008).
- [X] T014 [P] Unit test `backend/tests/unit/test_agent_loop.py`: the loop stops at ≤ 8
  iterations and the token budget (FR-006/SC-008); a non-allowlisted tool is rejected
  (FR-007); a failing tool yields a structured error and never a raw trace (FR-010).
- [X] T015 Create `backend/app/services/agent/loop.py`: the bounded ReAct loop —
  JSON-action protocol via `infra/llm.py` `complete()`, allowlist dispatch through the
  registry, per-iteration token accounting against the budget, forced synthesis on cap,
  structured tool-error handling (FR-006/010, research R1). (Depends on T013.)
- [X] T016 Wire the embedder singleton: build/init the embedder in
  `backend/app/core/lifespan.py` (embedder construction + teardown only). Chat and goals
  router registration in `backend/main.py` happens in their own phases (T019, T038), not
  here. (Depends on T008.)

**Checkpoint**: schema migrated; agent loop + registry + rails + rate limiter + session
memory + embedder all exist and the loop's unit test passes.

---

## Phase 3: User Story 1 - Ask about my own money and get an exact answer (Priority: P1) 🎯 MVP

**Goal**: A signed-in user chats and gets exact, streamed answers; enumerable turns
(balance, subscriptions, simple category total) are answered deterministically off the
agent.

**Independent Test**: Ask the three enumerable questions on a seeded account; each answer
matches the figure computed directly from the data and is marked `route: "deterministic"`.

- [X] T017 [P] [US1] Unit test `backend/tests/unit/test_router.py`: balance, subscriptions,
  and single-category-total turns classify `deterministic` with the correct exact figure;
  ambiguous/multi-step turns classify `agent`; the route is recorded for the % off-agent
  metric (FR-003/005, SC-001/006).
- [X] T018 [US1] Create `backend/app/services/agent/router.py`: high-precision intent
  matchers for the enumerable turns, each backed by an exact query through the existing
  transactions/analytics repositories under the RLS session, with fixed response
  templates; emits a `RouterDecision` and logs the route (FR-003/005, research R2).
- [X] T019 [US1] Create `backend/app/api/chat.py`: `POST /chat` (streamed) — runs
  `rails.check_input` → `session_memory` load → router; enumerable → template, else →
  agent loop; `rails.check_output`/`redact` before egress; streams deltas + a final event
  with `route`/`citations`/`bounded`; writes the turn back to session memory; register the
  chat router in `backend/main.py` (FR-001/002, contracts/http-api). (Depends on T018,
  T015, T012, T010.)
- [X] T020 [P] [US1] Frontend chat surface: create `frontend/src/api/chatApi.ts` (POST
  `/chat` streaming reader over `fetch`), `frontend/src/pages/Chat.tsx`,
  `frontend/src/components/ChatInput.tsx`, and `frontend/src/components/ChatMessage.tsx`;
  add a Chat link to `frontend/src/components/NavBar.tsx` and a `/chat` route under
  `RequireAuth` in `frontend/src/App.tsx`.
- [X] T021 [P] [US1] Frontend test `frontend/src/pages/Chat.test.tsx`: sending a message
  calls the streaming `chatApi` (mocked) and renders streamed deltas incrementally into a
  `ChatMessage`; the input disables while a response is in flight (FR-001/002).
- [X] T022 [US1] Integration test `backend/tests/integration/test_chat_enumerable.py`:
  `POST /chat` for each enumerable question returns the exact figure and
  `route: "deterministic"` with no agent/LLM span (FakeLLM). (Depends on T019.)

**Checkpoint**: chat works end-to-end; enumerable turns answered exactly and cheaply. MVP.

---

## Phase 4: User Story 2 - Get cited financial-literacy guidance (Priority: P2)

**Goal**: Knowledge questions are answered from the shared corpus with citations; empty
retrieval yields a no-answer.

**Independent Test**: An in-corpus question returns a cited answer; an off-corpus question
returns an honest no-answer with no fabricated citation.

- [X] T023 [P] [US2] Unit test `backend/tests/unit/test_rag_retrieval.py`: hybrid fusion
  ranks the relevant passage into the top results; an empty/below-floor result returns
  `no_answer`; a grounded answer carries ≥ 1 citation; no personal figures appear
  (FR-013/014, SC-004, research R4/R5).
- [X] T024 [P] [US2] Create `backend/app/services/rag/chunking.py`: heading-aware splitter
  producing passages with `heading_path` + `ordinal` (research R9).
- [X] T025 [US2] Create `backend/app/repositories/knowledge_repo.py`: dense cosine top-k
  (pgvector) and sparse `ts_rank` top-k (Postgres full-text) queries over the shared
  passages (research R4).
- [X] T026 [US2] Create `backend/app/services/rag/retrieval.py`: Reciprocal Rank Fusion of
  dense+sparse, the no-answer score floor, and citation assembly (FR-013/014, research
  R4/R5). (Depends on T025, T008.)
- [X] T027 [US2] Create `backend/app/services/rag/ingest.py` + `backend/scripts/ingest_corpus.py`:
  offline embed of `rag-corpus/*.md` into `knowledge_documents`/`knowledge_passages`,
  idempotent by content hash (research R9). (Depends on T024, T025, T008.)
- [X] T028 [US2] Create `backend/app/services/agent/tools/knowledge.py`:
  `search_financial_knowledge` (Pydantic IO) over `retrieval.py`, returning passages +
  citations or `no_answer`; register it in the allowlist; wire `synthesis.txt` so the
  agent's grounded answer cites sources (FR-011/013/014, contracts/tools). (Depends on
  T026, T013.)
- [X] T029 [P] [US2] Frontend: render citations in `frontend/src/components/ChatMessage.tsx`
  (a `Citation` chip per source: document + heading) from the final-event `citations`.
- [X] T030 [P] [US2] Frontend test `frontend/src/components/ChatMessage.test.tsx`: a final
  event with citations renders one chip per source (document + heading); an answer with
  empty `citations` renders none (FR-013).
- [X] T031 [US2] Gate 4 (RAG): create `backend/tests/golden/rag/triples.yaml` (~15
  question/relevant-passage/answer triples), `backend/tests/test_rag_gate.py` computing
  hit@5, MRR, and faithfulness (frozen judge with reported hand-label agreement) against
  `eval_thresholds.yaml` `rag.*`; fill the `rag.hit_at_5_min`/`mrr_min`/`faithfulness_min`
  nulls from the first measured run minus tolerance and record in `docs/DECISIONS.md`
  (SC-003, research R11). Record whether rerank/rewrite/metadata-filter each pay off
  (FR-015) and cut any that don't. (Depends on T028.)

**Checkpoint**: knowledge questions answered with citations; off-corpus → no-answer; Gate 4 green.

---

## Phase 5: User Story 3 - Ask a complex, multi-step money question (Priority: P2)

**Goal**: The agent reconciles transactions + forecast + goals + cited knowledge in one
bounded answer (the affordability flagship).

**Independent Test**: The affordability question produces one answer drawing on all four
sources with `route: "agent"` and `bounded: false` in a normal run.

- [X] T032 [P] [US3] Unit test `backend/tests/unit/test_tools_rls.py`: each read/analysis
  tool validates its Pydantic input, runs under the RLS session, and returns
  summaries/aggregates only (no identifiers) (FR-008/009/011, Art. II).
- [X] T033 [US3] Create `backend/app/services/agent/tools/reads.py`: `query_transactions`,
  `get_forecast`, `get_anomalies`, `get_subscriptions` over the existing analytics/
  transactions repositories (stored derived rows; `get_forecast` is a DB read), each with
  Pydantic IO; register all four (contracts/tools, research R8). (Depends on T013.)
- [X] T034 [US3] Create `backend/app/services/agent/tools/analysis.py`:
  `affordability_check` (composes forecast + recent spend + optional goal, exact numbers)
  and `what_if` (recomputes a projection under a hypothetical spend change); register both
  (FR-011, contracts/tools, research R8). (Depends on T033.)
- [X] T035 [US3] Integration test `backend/tests/integration/test_affordability.py`: the
  affordability question yields one answer incorporating transactions, forecast, goal, and
  cited guidance, `route: "agent"`, within the iteration cap (SC-005/008). (Depends on
  T034, T028.)

**Checkpoint**: multi-step affordability/what-if reconciliation works and stays bounded.

---

## Phase 6: User Story 4 - Track goals and have the agent remember context (Priority: P3)

**Goal**: Goals CRUD (chat + REST); in-session continuity; audited durable memory.

**Independent Test**: Set a goal in chat → it lists; refer back mid-session without
restating; ask to remember a preference → a durable memory + an audit row exist; short-term
context expires after 30 min while goals/memories persist.

- [X] T036 [P] [US4] Unit test `backend/tests/unit/test_memory_audit.py`: `write_memory`
  creates a user-scoped memory with an embedding AND one `audit_log` row; recall is
  user-filtered; no durable memory is created by any other path (FR-018/019, SC-010).
- [X] T037 [P] [US4] Create `backend/app/repositories/goals_repo.py` (create/list/update,
  status transitions, RLS-scoped) and `backend/app/repositories/memory_repo.py`
  (user-scoped vector upsert + nearest-neighbour recall).
- [X] T038 [US4] Create `backend/app/api/goals.py`: `GET/POST/PATCH /goals` per
  contracts/http-api, validating required fields and status transitions; register the
  goals router in `backend/main.py` (FR-016). (Depends on T037, T009.)
- [X] T039 [US4] Create `backend/app/services/agent/tools/goals.py` (`get_goals`,
  `set_goal`) and `backend/app/services/agent/tools/memory.py` (`write_memory` → embed +
  store + audit row, rate-limited); register all three in the allowlist (FR-016/018/019/020,
  contracts/tools). (Depends on T037, T008, T011, T013.)
- [X] T040 [US4] Integration test `backend/tests/integration/test_goals_memory.py`: goal
  created via chat lists through `/goals`; an in-session follow-up uses prior context;
  durable memory persists with an audit row; short-term context expires on TTL (FR-016/017,
  SC-010). (Depends on T039, T038, T019.)

**Checkpoint**: goals + session continuity + audited durable memory all work.

---

## Phase 7: User Story 5 - Make changes by talking to the agent (Priority: P3)

**Goal**: Conversational `add_transaction` and `reclassify_transaction`, validated, scoped,
and rate-limited.

**Independent Test**: Add a transaction via chat → it appears; reclassify → human
provenance; a missing field is rejected; the 11th write in a minute is throttled.

- [X] T041 [P] [US5] Unit test `backend/tests/unit/test_write_tools.py`: `add_transaction`
  reuses the ingestion path (in-memory parse/scrub, provenance), `reclassify_transaction`
  records a `human`-provenance correction, invalid args are rejected with a readable
  message, and the 11th write/min is throttled (FR-020/021, SC writes).
- [X] T042 [US5] Create `backend/app/services/agent/tools/writes.py`: `add_transaction`
  (via the Phase-3 ingestion service) and `reclassify_transaction` (writes a `Correction`
  with `confirmed_by_human=true`, provenance `human`); both rate-limited and RLS-scoped;
  register both in the allowlist (FR-020/021, contracts/tools, research R8). (Depends on
  T013, T011.)

**Checkpoint**: all five stories independently functional.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [X] T043 [P] Gate 3 (tool-selection): create `backend/tests/golden/tool_selection/cases.yaml`
  (~15 turns → expected route/tool across the full allowlist) and
  `backend/tests/test_tool_selection_gate.py` asserting selection accuracy ≥
  `eval_thresholds.yaml` `router.tool_selection_accuracy_min`; fill that null from the
  first measured run minus tolerance and record in `docs/DECISIONS.md` (SC-002, research
  R11). (Depends on all tool phases: T033, T034, T039, T042, T028.)
- [X] T044 [P] Integration test `backend/tests/integration/test_chat_isolation.py`: as user
  A then user B, no tool ever returns the other user's transactions, goals, or memories
  (FR-009/024, SC-007).
- [X] T045 [P] Observability: add structlog spans with token/cost fields on every
  LLM/tool/retrieval call across `services/agent/` and `services/rag/` (Art. V).
- [X] T046 [P] Wire CI in `.github/workflows/ci.yml`: ensure the backend job runs the new
  unit tests under `backend/tests/unit/` (extend the existing `pytest tests/unit -q` step
  or confirm it covers them) **and** add explicit steps for the two gates
  (`pytest tests/test_tool_selection_gate.py tests/test_rag_gate.py -q`) plus the new
  `tests/integration` tests; all run with `FakeLLM`/`FakeEmbedder` and only the Postgres
  service — no compose stack (Art. V). Add a frontend `Test` step if not already present.
- [X] T047 [P] Append a Phase 4 section to `docs/DECISIONS.md` recording every number:
  agent caps (8/16k), session TTL (30 min), write rate (10/min), embedding dim (768) and
  the embedder-reuses-`gemini_api_key` decision, JSON-action loop choice (R1), hybrid+RRF
  + no-answer floor (R4/R5), the filled router/RAG gate thresholds, and the
  rerank/rewrite/metadata-filter justify-or-cut outcomes (FR-015, Art. V).
- [X] T048 Run `ruff check .`, `mypy .`, and `pytest -q` in `backend/`, plus
  `npm run typecheck`/`lint`/`test` in `frontend/`; fix until all are zero-error and green.
  (Depends on all prior.)
- [X] T049 Run `specs/006-agent-rag/quickstart.md` scenarios 1–8 against the live stack;
  confirm each acceptance criterion. (Depends on T048.)
- [X] T050 [P] Refresh the knowledge graph with `graphify update .` per the constitution
  workflow.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies — T002, T003 parallel after/with T001.
- **Foundational (Phase 2)**: depends on Setup — BLOCKS all user stories. Domain
  (T004–T006) → migration (T007); embedder/schemas/rails/ratelimit/session (T008–T012)
  parallel; registry (T013) → loop (T015) with its test (T014); embedder lifespan wiring
  (T016).
- **User Stories (Phase 3–7)**: all depend on Foundational. US1 is the MVP. US2 (RAG) is
  independent of US3/US4/US5. US3 read/analysis tools, US4 goals/memory tools, and US5
  write tools are independent tool sets that each register into the existing loop. US3's
  affordability integration test (T035) also uses the US2 knowledge tool (T028) for the
  cited portion.
- **Polish (Phase 8)**: Gate 3 (T043) depends on all tool phases; the rest after the
  stories they cover.

### Parallel Opportunities

- Setup: T002, T003 parallel after T001.
- Foundational: T005, T006 parallel after T004; T008–T012 all parallel; T014 alongside T015.
- US1: T017 (test) and T020 (frontend) parallel; T018 → T019 → T022 sequential (shared
  backend path); T021 (frontend test) after T020.
- US2: T023 (test), T024 (chunking), T029 (frontend) parallel; T025 → T026 → T027/T028 →
  T031; T030 (frontend test) after T029.
- US3: T032 (test) parallel; T033 → T034 → T035.
- US4: T036 (test) parallel; T037 → T038/T039 → T040.
- US5: T041 (test) parallel; → T042.
- Polish: T043, T044, T045, T046, T047, T050 parallel; T048 then T049 sequential at the end.

---

## Implementation Strategy

### MVP First (User Story 1 only)

Setup → Foundational → US1 → **STOP and validate**: chat answers the three enumerable
questions exactly and deterministically. Demo-able conversational MVP.

### Incremental Delivery

Foundational → US1 (chat + exact enumerable) → US2 (cited knowledge + Gate 4) → US3
(affordability reconciliation) → US4 (goals + memory) → US5 (conversational writes) →
Polish (Gate 3, isolation, observability, CI, decisions). Each story adds value without
breaking the previous.

### Notes

- [P] = different files, no incomplete dependencies.
- Tests precede or accompany their implementation within each story (Art. V). Backend unit
  tests live under `backend/tests/unit/`, gate tests under `backend/tests/`, integration
  under `backend/tests/integration/`; frontend tests are co-located `*.test.tsx`.
- Tools wrap existing Phase 1–3 services; no business logic is reimplemented.
- Personal numbers come from exact SQL, never RAG; citations always; no-answer on empty
  retrieval — assert these in every relevant test.
- All prompts live under `backend/prompts/`; all tuned numbers land in `docs/DECISIONS.md`.
- Commit after each task or logical group; stop at any checkpoint to validate a story.
