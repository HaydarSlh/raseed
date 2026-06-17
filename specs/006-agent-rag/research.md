# Research: Knowledge & the Agent (Phase 4)

Decisions resolving the Technical Context unknowns. Each is grounded in the
constitution (Art. IV/V), `docs/PLAN.md` (DESIGN E/F/H), the brief, and the five
clarifications recorded in `spec.md`. Numbers chosen here are recorded in
`DECISIONS.md` at implementation time.

## R1 — Agent loop: provider-agnostic JSON-action ReAct, not native function-calling

**Decision**: Implement the bounded agent as an in-process ReAct loop that prompts the
LLM (via the existing `infra/llm.py` adapter `complete()`) to emit a strict JSON
action — `{"tool": <name>, "args": {...}}` or `{"final": <answer>, "citations": [...]}`
— which the loop parses, validates against the tool's Pydantic schema, dispatches, and
feeds the observation back. Cap at **8 iterations** and a **~16k-token** running budget
(FR-006); on either cap, force a synthesis turn and return the best bounded answer.

**Rationale**: The Phase-1 adapter is a text-completion boundary with Gemini→Grok
failover; Grok failover and the `FakeLLM` test double do not share Gemini's native
function-calling schema. A JSON-action protocol keeps one code path across all three,
stays deterministic under `FakeLLM` (so CI never calls a hosted model), and keeps the
allowlist + Pydantic validation in *our* code where Art. IV requires it — not delegated
to a provider. Token accounting is done in the loop from the adapter's usage fields.

**Alternatives considered**: Gemini native function-calling (rejected — provider-locked,
breaks on Grok failover, moves validation outside our boundary); LangChain/LlamaIndex
agent (rejected — heavy dependency, opaque control flow, conflicts with the "one bounded
loop we own" mandate).

## R2 — Deterministic router: rule/keyword intent match → exact SQL + template

**Decision**: A `services/agent/router.py` classifies each turn before the agent. A
small set of high-precision intent matchers (normalized keyword + light pattern rules)
recognize the enumerable turns — current balance, subscriptions list, single-category
total (with an optional time window) — and answer them with an exact repository query
and a fixed response template, no LLM call. Everything else (and anything the matchers
flag low-confidence) falls through to the agent. The router records a decision row
(`deterministic` vs `agent`) per turn so coverage (% off-agent) is measurable (FR-005,
SC-006).

**Rationale**: Enumerable turns must be correct and cheap (SC-001) and must never be
templated when ambiguous (edge case). A deterministic matcher is 100%-reproducible,
trivially unit-testable, and is exactly what the tool-selection golden set (Gate 3)
asserts. Keeping it rule-based (not an LLM classifier) means zero cost and zero variance
on the hot path.

**Alternatives considered**: LLM-based intent classification (rejected — cost/variance on
the cheap path, and it would itself need the golden set to gate); embedding-similarity
routing (rejected — overkill for ~3 enumerable intents, harder to assert deterministically).

## R3 — Embeddings: hosted Gemini embedding via the adapter, `vector(768)`

**Decision**: Add an `embed(texts) -> list[vector]` method on the LLM adapter boundary
(`infra/llm.py` / `infra/embeddings.py`) backed by a hosted Gemini embedding model
(768-dim), with a `FakeEmbedder` deterministic double (hash→seeded vector) for CI/local.
Store `vector(768)` in `knowledge_passages.embedding` and `memory.embedding`. Embedding
calls are TTL-cached (Art. V).

**Rationale**: Hosted embeddings keep the serving path lean (no torch/sentence-transformers
in any image — Art. III). 768 dims is the standard Gemini text-embedding width and a good
quality/size balance for a small corpus. Routing embeddings through the same adapter
boundary keeps "no module imports a provider SDK except the adapter" intact and gives a
deterministic fake for stack-independent CI.

**Alternatives considered**: Local `sentence-transformers` (rejected — pulls torch into an
image, violates Art. III lean-serving); OpenAI embeddings (rejected — off the fixed LLM
stack); 1536-dim models (rejected — unjustified storage/compute for this corpus size).

## R4 — Hybrid retrieval: dense (pgvector cosine) + sparse (Postgres full-text) via RRF

**Decision**: Retrieve top-k by dense cosine over `pgvector` *and* top-k by Postgres
native full-text (`tsvector` + `ts_rank`), then fuse with Reciprocal Rank Fusion to a
final ranked list. The corpus is shared (no user filter); memory retrieval uses the same
dense path but **user-filtered** by RLS. Reranking, query rewriting (Flash-Lite), and
metadata filtering are each added **only if** they measurably improve the RAG golden set
(FR-015) — baseline hybrid is built first, each enhancement is A/B'd against the golden
set, and the delta is recorded in `DECISIONS.md`; an enhancement that doesn't pay is cut
(matches the PLAN trim ladder: "rerank if unjustified by the number").

**Rationale**: Hybrid beats either signal alone on short factual finance queries (exact
term matches like "APR" + semantic paraphrase). Postgres full-text needs no new
dependency and lives in the same store as the vectors, so one query path, one
transaction. RRF is parameter-light and robust. Building baseline-first and gating each
enhancement on a number is precisely what FR-015/Art. V demand.

**Alternatives considered**: Dense-only (rejected — misses exact-term finance jargon);
external vector DB / BM25 service (rejected — new infra, off-stack); always-on reranker
(rejected — must be justified by the golden-set number first).

## R5 — No-answer gate: score floor on the fused top result

**Decision**: After fusion, if the top passage's similarity is below a tuned floor (or
the result set is empty), the system returns the `no_answer.txt` response — no synthesis,
no fabricated citation (FR-014). The floor is tuned against the RAG golden set + a set of
deliberately off-corpus questions (SC-004 requires 100% no-answer on those) and recorded.

**Rationale**: A grounded RAG system must refuse rather than invent (Art. IV). Tuning the
floor on both in-corpus triples and off-corpus negatives makes the gate measurable and
prevents both over-refusal and hallucinated citations.

**Alternatives considered**: LLM self-assessment of relevance (rejected — variance, cost,
not deterministically gateable); fixed top-k with no floor (rejected — would synthesize
from irrelevant passages on off-corpus questions).

## R6 — Short-term memory: Redis hash per session, 30-min sliding TTL

**Decision**: Store the rolling conversation context as a Redis structure keyed by
session, with a **30-minute sliding (idle) TTL** refreshed on each turn (clarification
Q3, FR-017). Durable goals/memories are in Postgres and unaffected by expiry. The chat
endpoint reads/writes this context around the router+agent call.

**Rationale**: Redis is the mandated session store; a sliding TTL gives "expires after 30
min of inactivity" exactly. Keeping short-term context out of Postgres matches the
ephemeral-chat clarification (Q1) — nothing to persist or later erase.

**Alternatives considered**: Postgres-backed conversation table (rejected — contradicts the
ephemeral-chat decision, adds erasure surface); in-process memory (rejected — lost on
restart, not multi-worker safe).

## R7 — Per-user write rate limit: Redis fixed-window counter, 10/min

**Decision**: A `services/agent/ratelimit.py` increments a Redis counter keyed by
`user_id` + minute window; the 11th write in a window is refused with a readable message
(FR-020, clarification Q4). Applies to `add_transaction`, `set_goal`,
`reclassify_transaction`, `write_memory`.

**Rationale**: A fixed-window Redis counter is simple, fast, multi-worker-correct, and
trivially asserted in the FR-020 burst test. 10/min is generous for genuine
conversational use and firmly caps a runaway loop.

**Alternatives considered**: Token-bucket (rejected — more moving parts than needed for a
coarse safety cap); in-DB rate check (rejected — write contention, slower hot path).

## R8 — Tools wrap existing services under one RLS session

**Decision**: Each tool is a thin function with a Pydantic input schema, registered in an
allowlist registry, that runs against the request's `get_rls_session`. Read tools
(`query_transactions`, `get_forecast`, `get_anomalies`, `get_subscriptions`) call the
existing analytics repositories (stored derived rows — `get_forecast` is a DB read, not a
Prophet fit). Write tools reuse the Phase-3 ingestion service (`add_transaction`) and the
corrections path (`reclassify_transaction` → `confirmed_by_human=true`, provenance
`human`). `affordability_check`/`what_if` compose reads + simple arithmetic in the service
layer. Only summaries/aggregates from tool outputs enter the LLM context — never raw rows
or identifiers (Art. II).

**Rationale**: Reuse keeps one source of truth for ingestion scrubbing, the confidence
gate, and provenance (no divergent second path). RLS-scoped sessions make cross-user
leakage structurally impossible (SC-007). Pydantic validation at the tool boundary is the
Art. IV mandate.

**Alternatives considered**: Tools issuing raw SQL (rejected — bypasses repo-layer scoping
and reuse); passing full transaction rows to the LLM (rejected — Art. II identifier-egress
violation).

## R9 — Corpus: curated markdown in `rag-corpus/`, heading-aware chunking, offline ingest

**Decision**: Assemble an openly-licensed financial-literacy corpus (CFPB / MoneyHelper-
class consumer guidance + the project's own explainers) as markdown under `rag-corpus/`,
with a `SOURCES.md` recording each item's license. Chunk heading-aware (split on markdown
headings, keep heading path as passage metadata for citation). An **offline** script
(`scripts/ingest_corpus.py`) embeds passages and upserts them into `knowledge_passages`.
Re-running is idempotent (content hash per passage).

**Rationale**: Heading-aware chunks keep passages self-contained and give a natural
citation label (document + heading). Offline ingest keeps embedding cost off the request
path and out of CI; the corpus is shared and non-personal, so it carries no RLS concern.
Markdown keeps the corpus reviewable in git.

**Alternatives considered**: Fixed-size token chunks (rejected — splits mid-concept, worse
citations); ingesting at request time (rejected — cost + latency on the hot path); PDF
scraping (rejected — licensing/cleanliness risk; prefer openly-licensed text).

## R10 — Rails hook points: no-op middleware + redaction call site in the chat path

**Decision**: The chat path calls `rails.check_input(text)` before routing and
`rails.check_output(answer)` + `rails.redact(payload)` before any egress/LLM call — all
no-ops returning their input this phase (FR-022). Phase 6 fills the bodies without
re-plumbing the path.

**Rationale**: Wiring the call sites now prevents the rework the PLAN explicitly calls out
(DESIGN E "rails hook points (no-op) ship with the chat path in Phase 4; Phase 6 fills
them"). A no-op keeps Phase 4 behavior unchanged while the seam exists.

**Alternatives considered**: Adding rails later (rejected — forces re-threading the chat
path through new checkpoints, the exact rework the hook points exist to avoid).

## R11 — Gates #3 and #4: committed golden sets, FakeLLM, thresholds in eval_thresholds.yaml

**Decision**: Gate 3 (tool-selection) reads `tests/golden/tool_selection/cases.yaml`
(~15 turns → expected route/tool) and asserts selection accuracy ≥
`router.tool_selection_accuracy_min`. Gate 4 (RAG) reads `tests/golden/rag/triples.yaml`
(~15 question/relevant-passage/answer triples) and reports hit@5, MRR, and faithfulness
against `rag.hit_at_5_min` / `mrr_min` / `faithfulness_min`. Faithfulness uses a frozen
judge (or RAGAS) with a reported hand-label agreement rate. All currently-`null`
thresholds in `eval_thresholds.yaml` are filled from the first real measured run minus a
committed tolerance, recorded in `DECISIONS.md`. Both gates run with `FakeEmbedder`/a
fixed retrieval index so CI never calls a hosted model or starts the stack (Art. V).

**Rationale**: This is the acceptance criterion of the phase (brief) and the Art. V "gates
in eval_thresholds, regression blocks merge, CI stack-independent" mandate. Seeding
thresholds from a real run keeps them honest and ratcheting.

**Alternatives considered**: Live-API evaluation in CI (rejected — non-deterministic,
violates stack-independence); hand-wavy "looks good" acceptance (rejected — Art. V requires
a number).
