# CLAUDE.md — Raseed master context

Raseed (رصيد, "balance") is a B2C personal-finance intelligence platform:
statement upload -> ingestion pipeline (fine-tuned categorizer, Prophet forecaster,
anomaly + recurring detectors) -> isolated per-user data -> a bounded tool-calling
agent grounded in exact queries + RAG over financial-literacy knowledge -> a full
ML lifecycle (human corrections -> gated retrain -> drift detection -> Slack alerts).

## Authoritative documents (in priority order)
1. The Spec Kit constitution (engineering invariants — always wins).
2. The active phase's spec/plan/tasks under `specs/`.
3. `docs/PLAN.md` — full design rationale and every agreed decision.
4. `briefs/` — the phase briefs the specs were generated from.

## Fixed stack (do not substitute)
React (Vite) SPA · FastAPI (async, layered: api/services/repositories/domain/infra)
· Postgres + pgvector with per-user RLS (session var `app.user_id`, reset on
connection release) · fastapi-users (JWT) · Redis (sessions + RQ) · MinIO (model
artifacts only — never user files) · Vault (all secrets) · model-server container
(onnxruntime + numpy, lean, refuse-to-boot hash check) · trainer container (heavy,
torch, `training` compose profile, RQ `training` queue) · light worker (stats job,
drift, Slack webhook) · LLM adapter: Gemini Flash-Lite (mechanical) / Gemini Flash
(synthesis) -> Grok failover · Alembic · structlog + request IDs · GitHub Actions.

## Non-negotiable invariants (summary — full text in the constitution)
- Every query user-scoped; RLS is the backstop, not the only line.
- Raw statement files are never persisted; PAN/IBAN scrubbed in the parser.
- Only human-confirmed labels train the model; LLM relabels are quarantined.
- No torch in any serving image; the trainer is the single heavy image.
- The user's numbers come from exact SQL, never from RAG.
- Prompts live in `prompts/`; secrets resolve from Vault; nothing hardcoded.
- Webhook payloads carry ops signals only — never user-level transaction data.

## Navigation
Graphify is installed project-scoped. Prefer `/graphify query "<question>"` and
`/graphify path` over grepping; refresh with `/graphify .` after each phase.
Phase 0 stubs every file with a header comment stating its single responsibility —
trust those headers as the file map.

## Workflow
One phase = one Spec Kit feature (briefs/phase-N-*.md). Order in COMMANDS.md.
Each phase ships its tests and ends with CI green and a graphify refresh.

<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan:
`specs/004-ingestion-analytics/plan.md` (Phase 3 — ingestion & analytics: one shared ingestion service, per-user forecaster + anomaly/recurring detectors, privileged population-stats job, dashboard).
<!-- SPECKIT END -->

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
