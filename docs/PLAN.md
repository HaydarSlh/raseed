# RASEED — Implementation Plan v1.1 (authoritative)

Raseed (رصيد, "balance") — a B2C personal finance intelligence platform.
This document is the single source of design truth. The phase briefs in
`briefs/` derive from it; resolve every /speckit.clarify question from here.
v1.1 = v1.0 (the PDF) + post-audit refinements, marked inline.

## MISSION
A user signs up, gets an isolated account, uploads bank/card statements. An
ingestion pipeline categorizes every transaction with a developer-fine-tuned
model, forecasts cash flow, detects anomalies and subscriptions. A bounded
tool-calling agent answers money questions grounded in exact queries over the
user's own data, retrieves financial-literacy guidance through RAG, tracks
goals, runs what-if scenarios. Corrections feed a gated retraining loop with
drift detection — a full ML lifecycle, visible on an ops page, alerting to
Slack. Two hard problems: the lifecycle (improving from human feedback without
poisoning itself on LLM guesses) and isolation (enforced by the database).
Informational tool — never licensed financial advice.

## STACK (fixed)
React (Vite) SPA · FastAPI async layered backend · Postgres + pgvector with
per-user RLS (session var, reset on release) · fastapi-users JWT · Redis
(sessions + RQ) · MinIO (model artifacts ONLY) · Vault · lean model-server
(onnxruntime) · trainer (heavy, torch, profile `training`) [v1.1: split from the
light worker] · light worker (stats job, drift, Slack webhook) · LLM adapter:
Gemini Flash-Lite (mechanical) / Gemini Flash (synthesis) -> Grok failover
[v1.1: two-tier routing confirmed] · Alembic · structlog · GitHub Actions ·
Graphify (project-scoped) for codebase navigation.

## DESIGN A — Isolation
user_id on every row; RLS via per-request set_config, reset on connection
release; repo-layer scoping as depth; JWT-derived identity only; is_operator
boolean (not RBAC); right-to-erasure purging rows + memory vectors + sessions
(no blob component — raw files never persisted), audit-logged, with the
model-unlearning limitation documented; data minimization to the LLM; scaling
story in DESIGN.md (retrain cadence, Prophet per-user cost, LLM cost/user).

## DESIGN B — Ingestion & categorizer
One shared ingestion service behind upload page, manual form, and agent tool.
In-memory parse, PAN/IBAN scrub in the parser, raw file discarded. Rules layer
(weak supervision, provenance=rule). Fine-tuned DistilBERT trained offline IN
COLAB ON GPU [v1.1: explicit]; ONNX + model card + SHA; lean model-server with
refuse-to-boot (guard activates in Phase 2 — Phase 0 stub serves a "no model
loaded" healthz [v1.1 fix]). Three approaches, one number: TF-IDF+LR vs
DistilBERT vs Gemini zero-shot — macro-F1, per-class F1, latency, cost.
Operating threshold by explicit rule. Provenance: rule|model|llm|human.
Frozen holdout committed via Git LFS; CI artifacts come from LFS/release
assets, never the running stack [v1.1 fix].

## DESIGN C — ML lifecycle
Human-confirmed labels only train; LLM relabels quarantined until confirmed.
Trigger: 100 corrections OR 14 days (cooldown), manual button, demo
threshold 10. Trainer service: partial-unfreeze retrain on CPU in-stack
[v1.1: Colab = initial foundation training only; automated retrains never
leave the stack]; new ONNX -> MinIO. Champion/challenger on the frozen
holdout; model_registry table (MLflow = future); HIL promotion by operator;
model-server reload. Drift: mean confidence + correction rate (primary), PSI
on category distribution + new-merchant rate (secondary); simulate_drift.py
makes it demonstrable; CI gate runs with the training profile enabled
[v1.1 fix]. Ops page: charts, drift status, retrain history, buttons.
SLACK webhook [v1.1: provider fixed], URL from Vault, ops signals only —
never user-level transaction data; timeout/retry/backoff, non-blocking.

## DESIGN D — Forecaster & detectors
Decomposition: recurring projected deterministically; only variable
discretionary spend is forecast. balance = current + known income - known
recurring - forecast discretionary. v1 assumes recurring income (variable
income = future work). Prophet per user (native intervals -> likely_range);
day-of-week baseline it must beat (MAE/MAPE); cold-start fallback blending
day-of-week averages with a population prior computed by a PRIVILEGED
background job into a global anonymized stats table (user-scoped sessions
must not compute cross-user aggregates). Anomaly: robust z/IQR + duplicate
rule. Recurring: cadence + amount regularity, price-increase flags. Derived
data invalidated & recomputed on write; get_forecast is a DB read. Forecaster
CI gate runs on a committed fixture under tests/golden/forecasting [v1.1 fix].
Global LightGBM = future work.

## DESIGN E — Router + agent
Deterministic router for enumerable turns (exact query + template); bounded
agent (iteration/token caps, allowlist, Pydantic inputs, RLS-scoped tools)
for ambiguous/multi-step turns; measure % kept off the agent. Tools:
query_transactions, get_forecast, get_anomalies, get_subscriptions,
affordability_check, what_if, search_financial_knowledge, get_goals/set_goal,
write_memory, add_transaction, reclassify_transaction. Writes rate-limited.
Redis short-term memory (justified TTL); goals table; explicit audited
write_memory into user-scoped pgvector. Prompts in prompts/. Rails hook
points (no-op) ship with the chat path in Phase 4; Phase 6 fills them
[v1.1 fix]. Flash-Lite mechanical / Flash synthesis / Grok failover.

## DESIGN F — RAG
Openly-licensed financial-literacy corpus (CFPB/MoneyHelper-class + own
explainers); heading-aware chunking; hosted embeddings into pgvector; shared
corpus (memory vectors are the user-filtered ones). Hybrid retrieval +
rerank/rewrite/metadata-filter only where a golden-set number justifies each.
Citations always; no-answer gate. RAG never answers numeric personal
questions — exact SQL does.

## DESIGN G — Security & compliance
PAN/IBAN scrub at the parser; no raw uploads persisted. In-process rails
(injection/jailbreak heuristics, on-domain, no-licensed-advice); PII redaction
before logs/traces/LLM calls + fake-key test; red-team CI (injection,
cross-user, prompt extraction); per-user rate limits; Vault day 1 (env-file =
first trim rung); erasure path. NeMo sidecar = future work.

## DESIGN H — Engineering & CI
Layered, async, DI, lifespan singletons, pydantic-settings extra='forbid',
exception hierarchy, tenacity everywhere external. Caching: lru_cache
deterministic; TTL only for RAG/embeddings; transaction-derived data
invalidated on write. structlog + request IDs + spans with token/cost fields
(per-user cost REPORTING = future). GitHub Actions: lint, type-check, build,
then the eight gates; thresholds committed day 1.

## CI GATES
1 categorizer F1 (holdout, beats baseline) · 2 forecaster MAE vs baseline
(fixture) · 3 tool-selection golden set · 4 RAG golden set (hit@5, MRR,
faithfulness) · 5 red-team · 6 redaction · 7 drift-fire (training profile on)
· 8 compose smoke test.

## PHASES (each = one Spec Kit feature; briefs in briefs/)
0 skeleton & map · 1 foundation (auth/tenancy/infra) · 2 categorizer (Colab
GPU -> ONNX -> lean serving) · 3 ingestion & analytics · 4 knowledge & agent ·
5 lifecycle & ops (Slack) · 6 security & compliance · 7 evals & release.
Mapping to the 5-day schedule: P0-1 day1 · P2-3 day2 · P4 day3 · P5 day4 ·
P6-7 days4-5; the rest of the two-week window is buffer.

## TRIM LADDER (in order, if behind)
Vault -> env-file · rerank (if unjustified by the number) · semantic memory
(keep goals) · ops-page charts -> tables · what_if tool.

## FUTURE WORK
Plaid sync · global LightGBM · variable-income forecasting · B2B2C
multi-tenancy · MLflow · NeMo sidecar + service-to-service auth · per-user
cost reporting · latency budgets · full RBAC · deeper semantic memory ·
Arabic localization · per-user personalization · hyperparameter depth · ONNX
quantization · managed-Postgres deployment (Supabase/RDS) · external GPU
training service for full retrains.
