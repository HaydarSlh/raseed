<!--
SYNC IMPACT REPORT
==================
Version change: 1.0.0 → 1.1.0 (2026-06-19)
Bump rationale (MINOR): Clarified Art. III + Technology Stack to match the
  implemented ML lifecycle. The trainer container is a CPU sklearn→ONNX retrainer,
  NOT a torch image; torch/transformers run only OFFLINE (dev box/Colab) to build
  the initial champion. The core invariant (no torch in any serving image; lean
  serving path) is unchanged — this corrects stale stack wording, so MINOR not
  MAJOR. Migration: removed torch/transformers from trainer/pyproject.toml (they
  were declared but never imported by trainer/train.py and dragged a 3GB+ CUDA
  wheel stack into the image build). See DECISIONS.md 2026-06-19 row.

Prior version history:
Version change: (template, unversioned) → 1.0.0
Bump rationale: First concrete ratification of the constitution from the template
  placeholder. Initial adoption ⇒ MAJOR baseline 1.0.0.

Principles (filled from briefs/constitution.md, articles I–V):
  - [PRINCIPLE_1] → I. Layered, Async Architecture
  - [PRINCIPLE_2] → II. Isolation & Data Protection (NON-NEGOTIABLE)
  - [PRINCIPLE_3] → III. ML Lifecycle Integrity
  - [PRINCIPLE_4] → IV. Bounded Agent & Grounded RAG
  - [PRINCIPLE_5] → V. Quality & Operations

Added sections:
  - [SECTION_2_NAME] → Technology Stack & Constraints (fixed stack)
  - [SECTION_3_NAME] → Development Workflow (spec-driven, phased)
  - Governance (amendment, versioning, compliance review)

Removed sections: none (all template slots populated).

Templates requiring updates:
  ✅ .specify/templates/plan-template.md — "Constitution Check" gate is dynamic
     ("[Gates determined based on constitution file]"); aligns by reference, no edit.
  ✅ .specify/templates/spec-template.md — no constitution references; no edit.
  ✅ .specify/templates/tasks-template.md — no constitution references; no edit.
  ✅ .specify/templates/checklist-template.md — generic; no edit.

Follow-up TODOs: none. Ratification date set to 2026-06-12 (initial adoption).
-->

# Raseed Constitution

Raseed (رصيد, "balance") is a B2C personal-finance intelligence platform. Every
spec, plan, task, and line of code obeys the articles below. A task that violates
an article is wrong even if it works. This document supersedes all other practices.

## Core Principles

### I. Layered, Async Architecture

The backend is strictly layered and imports flow downward only:
`api/` (HTTP only) → `services/` (business logic) → `repositories/` (SQL only) →
`domain/` (Pydantic models); `infra/` holds external adapters. Routers MUST NOT
touch the database. Every I/O step (LLM, DB, HTTP) MUST be awaited (httpx, async
SQLAlchemy); `requests` and `time.sleep` are forbidden in a request path, and
independent reads run in parallel via `asyncio.gather`. Shared expensive objects
(model-server client, embedder, LLM adapter, DB engine) are lifespan singletons
injected with FastAPI `Depends`. One typed pydantic-settings class with
`extra='forbid'` is the single source of configuration truth and MUST fail at
startup on a missing required value. A domain exception hierarchy maps to
structured HTTP errors; users MUST never see a stack trace.

**Rationale:** Downward-only layering and async-everywhere keep the system
debuggable, testable, and able to fan out I/O without blocking; a single typed
config and exception surface eliminate whole classes of runtime surprises.

### II. Isolation & Data Protection (NON-NEGOTIABLE)

Every user-data row carries `user_id`, derived from the verified JWT only — never
from a request body. A per-request session variable (`set_config('app.user_id', …)`)
set by a FastAPI dependency drives Postgres RLS on every user table and MUST be
RESET on connection release; repository-layer filtering remains as defense in
depth (RLS is the backstop, not the only line). Raw statement files are NEVER
persisted: parsing happens in memory and PAN/IBAN are scrubbed in the parser
before anything reaches a store. MinIO holds model artifacts only — never user
data. Only summaries and aggregates may cross the LLM boundary; identifiers never
do, and PII redaction runs before anything leaves the service (logs, traces, LLM
calls). Webhook payloads carry ops signals only — never user-level transaction
data.

**Rationale:** Per-user isolation and the no-raw-file / no-PII-egress rules are
the platform's core trust contract; they are non-negotiable because a single
breach of them compromises every user at once.

### III. ML Lifecycle Integrity

Every transaction records label provenance: `rule | model | llm | human`. Only
human-confirmed labels are training data; LLM relabels are quarantined in a
reviewable queue until a human confirms them. The frozen holdout set is touched
only by the champion/challenger gate, and a retrained model is promoted ONLY if
it beats the champion AND an operator approves. No torch or transformers ship in
any serving image (model-server stays lean: onnxruntime + numpy). Torch and
transformers run ONLY offline — on a dev box or Colab — to fine-tune the initial
champion, which is exported to ONNX before it ever enters the stack; no container
installs them. The in-stack retrainer is a CPU-only sklearn→ONNX job (TF-IDF+LR
seeded from the champion), off the default compose profile (RQ `training` queue)
and never on a request path. Model artifacts ship with a model card and a pinned
SHA-256, and servers MUST refuse to boot on a hash mismatch.

**Rationale:** Training only on human-confirmed labels, gating promotion on a
clean holdout plus human sign-off, and refusing to boot mismatched artifacts keep
the model trustworthy and the serving path lean and reproducible.

### IV. Bounded Agent & Grounded RAG

The agent is one bounded tool-calling loop (explicit iteration and token caps)
behind a deterministic router. Tools come from an explicit allowlist, every tool
input is Pydantic-validated, and every tool runs under the caller's RLS context.
LLM-triggered writes (`add_transaction`, `reclassify`, `set_goal`) are
schema-validated, rate-limited, and user-scoped. The user's numbers come from
exact SQL queries, NEVER from RAG; RAG serves only the shared financial-knowledge
corpus, answers carry citations, and an empty retrieval produces a no-answer, not
an invention. Long-term memory is written only through an explicit `write_memory`
tool, every write is audit-logged, and memory retrieval is user-filtered at query
time. Prompts live in `prompts/` as version-controlled files — never inline
strings.

**Rationale:** A bounded, allowlisted, RLS-scoped agent plus the "numbers from SQL,
never from RAG" rule prevents the LLM from fabricating financial facts or escaping
user isolation while still allowing useful tool use.

### V. Quality & Operations

Every external call has a timeout and a tenacity retry/backoff; 4xx responses do
NOT retry and tool failures return structured errors. LLM failover order is
Gemini → Grok, inside the single adapter. Caching uses `lru_cache` for
deterministic in-process work and TTL caches for RAG retrieval and embedding
calls; anything derived from transactions is invalidated on write, never
time-expired. Observability is structlog JSON with request IDs across API, queue,
and worker, plus a span per LLM/tool/retrieval call carrying token and cost
fields. Every phase ships its tests; CI gates live in `eval_thresholds.yaml` and a
regression blocks merge. CI-required artifacts (model, fixtures, holdout) are
committed via Git LFS or release assets — CI NEVER depends on the running stack.
Secrets resolve from Vault at startup; nothing is hardcoded and `grep -r "sk-"`
over app code returns nothing (an env-file fallback is an explicitly documented
trim, not a silent default). Every design decision is backed by a number recorded
in `DECISIONS.md`.

**Rationale:** Timeouts, structured failover, write-invalidated caches, traced
cost, and stack-independent CI make the system operable and its quality
measurable; decisions backed by numbers keep the design honest.

## Technology Stack & Constraints

The stack is fixed and MUST NOT be substituted:

- **Frontend:** React (Vite) SPA.
- **Backend:** FastAPI (async, layered per Principle I), Alembic migrations.
- **Data:** Postgres + pgvector with per-user RLS (session var `app.user_id`,
  reset on connection release); fastapi-users (JWT); Redis (sessions + RQ).
- **Storage:** MinIO for model artifacts only — never user files.
- **Secrets:** Vault for all secrets.
- **ML serving:** model-server container (onnxruntime + numpy, lean,
  refuse-to-boot hash check); trainer container (CPU sklearn→ONNX retrain — no
  torch/transformers — `training` compose profile, RQ `training` queue); light
  worker (stats job, drift, Slack webhook). Transformer fine-tuning of the initial
  champion is an offline step (torch/transformers on a dev box/Colab), not a
  container.
- **LLM:** adapter over Gemini Flash-Lite (mechanical) / Gemini Flash (synthesis)
  with Grok failover.
- **Observability/CI:** structlog + request IDs; GitHub Actions.

Authoritative documents, in priority order: (1) this constitution — always wins;
(2) the active phase's spec/plan/tasks under `specs/`; (3) `docs/PLAN.md` — design
rationale and every agreed decision; (4) `briefs/` — the phase briefs the specs
were generated from.

## Development Workflow

Work is spec-driven and phased: one phase equals one Spec Kit feature
(`briefs/phase-N-*.md`), executed in the order given by `COMMANDS.md`. Phase 0
stubs every file with a header comment stating its single responsibility; those
headers are the trusted file map. Clarifications are resolved from `docs/PLAN.md`,
never improvised. Each phase ships its tests and ends with CI green and a graphify
refresh (`graphify update .`). Codebase navigation prefers the project knowledge
graph (`graphify query`, `graphify path`, `graphify explain`) over grepping.

## Governance

This constitution supersedes all other practices. When any document conflicts with
it, the constitution wins.

- **Amendments** MUST be documented in this file, justified with rationale, and —
  where they change behavior or stack — accompanied by a migration note and a
  corresponding entry in `DECISIONS.md`.
- **Versioning** follows semantic versioning of governance: MAJOR for backward-
  incompatible principle removals or redefinitions, MINOR for a new principle or
  materially expanded guidance, PATCH for clarifications and non-semantic edits.
- **Compliance review:** every PR and plan MUST verify compliance with these
  principles; the plan template's Constitution Check is the gate. Any complexity
  that appears to violate a principle MUST be justified in writing or removed.
- **Runtime guidance** for the implementation agent lives in `CLAUDE.md`; it
  elaborates but never overrides these articles.

**Version**: 1.1.0 | **Ratified**: 2026-06-12 | **Last Amended**: 2026-06-19
