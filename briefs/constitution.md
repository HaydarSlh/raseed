# Raseed Constitution — engineering invariants

Every spec, plan, task, and line of code in this project obeys the articles below.
A task that violates an article is wrong even if it works.

## I. Architecture
1. Layered backend: `api/` (HTTP only) -> `services/` (business logic) ->
   `repositories/` (SQL only) -> `domain/` (Pydantic models) ; `infra/` holds
   external adapters. Imports flow downward only; routers never touch the database.
2. Async all the way down: every I/O step (LLM, DB, HTTP) is awaited (httpx,
   async SQLAlchemy). Never `requests` or `time.sleep` in a request path.
   Independent reads run in parallel with `asyncio.gather`.
3. Dependency injection via FastAPI `Depends`; expensive shared objects
   (model-server client, embedder, LLM adapter, DB engine) are lifespan singletons.
4. One typed pydantic-settings class with `extra='forbid'` is the single source
   of configuration truth; required values fail at startup.
5. Domain exception hierarchy mapped to structured HTTP errors; users never see
   a stack trace.

## II. Isolation & data protection
6. Every user-data row carries `user_id`. A per-request session variable
   (`set_config('app.user_id', ...)`) set by a FastAPI dependency drives Postgres
   RLS policies on every user table, and is RESET on connection release (pooled
   connections persist it). Repository-layer filtering remains as depth.
7. `user_id` is derived from the verified JWT only — never from a request body.
8. Raw statement files are never persisted. Parsing happens in memory; PAN/IBAN
   are scrubbed in the parser before anything reaches a store.
9. MinIO holds model artifacts only — never user data.
10. Data minimization to the LLM: summaries and aggregates cross the boundary;
    identifiers never do. PII redaction runs before anything leaves the service
    (logs, traces, LLM calls).
11. Webhook payloads carry ops signals only — never user-level transaction data.

## III. ML lifecycle
12. Label provenance on every transaction: `rule | model | llm | human`.
13. Only human-confirmed labels are training data. LLM relabels are quarantined
    in a reviewable queue until a human confirms them.
14. The frozen holdout set is touched only by the champion/challenger gate.
    A retrained model is promoted only if it beats the champion, and promotion
    requires human (operator) approval.
15. No torch or transformers in any serving image (model-server stays
    onnxruntime + numpy, lean). The trainer container is the single deliberately
    heavy image, off the default compose profile, never on a request path.
    Initial full fine-tuning happens offline in Colab on GPU; in-stack retrains
    use a partial-unfreeze policy sized for CPU.
16. Model artifacts ship with a model card and pinned SHA-256; servers refuse to
    boot on a hash mismatch (guards activate in the phase that introduces the
    guarded artifact).

## IV. Agent & RAG
17. The agent is one bounded tool-calling loop (iteration + token caps) behind a
    deterministic router; tools come from an explicit allowlist, every tool input
    is Pydantic-validated, every tool runs under the caller's RLS context.
18. LLM-triggered writes (add_transaction, reclassify, set_goal) are
    schema-validated, rate-limited, and user-scoped.
19. The user's numbers come from exact SQL queries, never from RAG. RAG serves
    only the shared financial-knowledge corpus, answers carry citations, and an
    empty retrieval produces a no-answer, not an invention.
20. Long-term memory writes happen only through an explicit `write_memory` tool;
    every write is audit-logged; memory retrieval is user-filtered at query time.
21. Prompts live in `prompts/` as version-controlled files — never inline strings.

## V. Quality & operations
22. Every external call has a timeout and tenacity retry/backoff; 4xx do not
    retry; tool failures return structured errors. LLM failover order:
    Gemini -> Grok, inside the single adapter.
23. Caching: `lru_cache` for deterministic in-process work; TTL caches for RAG
    retrieval and embedding calls; anything derived from transactions is
    invalidated on write, never time-expired.
24. structlog JSON with request IDs across API, queue, and worker; a span per
    LLM/tool/retrieval call with token and cost fields.
25. Every phase ships its tests; CI gates live in eval_thresholds.yaml and a
    regression blocks merge. CI-required artifacts (model, fixtures, holdout)
    are committed via Git LFS or release assets — CI never depends on the
    running stack.
26. Secrets resolve from Vault at startup; nothing hardcoded; `grep -r "sk-"`
    over app code returns nothing. (Env-file fallback is an explicitly
    documented trim, not a silent default.)
27. Every design decision is backed by a number recorded in DECISIONS.md.
