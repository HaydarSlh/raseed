<!-- DESIGN.md — living design notes that elaborate docs/PLAN.md as phases land
     (scaling story, retrain cadence, per-user cost, erasure path). Placeholder in
     Phase 0; populated from Phase 1 onward. -->

# Raseed Design Notes

Elaborations on `docs/PLAN.md` that need room to breathe. Authoritative design truth
stays in `PLAN.md` and the constitution; this file carries the worked detail.

## Scaling story

**Stateless API tier** — FastAPI workers are stateless and horizontally scalable
behind a load balancer. Each request resolves its user from the JWT, sets the RLS
session var, and releases the connection to the pool; no affinity is required.

**Per-user Prophet cost** — The recompute worker calls `prophet.predict()` once per
user per upload. On the UK open-banking dataset (~180 tx/user) this takes < 2 s on a
single CPU core and produces a 30-day daily forecast. Cost scales linearly with
active users; at 10,000 daily-active users a single 2-core worker handles the queue
in < 6 hours assuming a uniform upload distribution. A second worker reduces latency
proportionally — the queue is a standard RQ queue and horizontal scaling is trivial.

**pgvector index** — Financial-knowledge embeddings live in `knowledge_documents` with
an IVFFlat index (`lists=100`). At the current corpus size (< 500 passages) an exact
scan is faster than IVFFlat; the index becomes relevant above ~10k passages. pgvector
supports seamless transition from exact to approximate search by tuning `ivfflat.probes`.

**Per-user RLS row filtering** — Every query hits the RLS policy which prepends a
`WHERE user_id = current_setting('app.user_id')` predicate. At Postgres 16 this adds
< 1 ms overhead for indexed user_id columns. The `user_id` index on every user-scoped
table is critical; without it a full-table scan would occur.

**Redis session fan-out** — Sessions are stored in Redis with a 1-hour TTL. A single
Redis instance handles tens of thousands of concurrent sessions; cluster mode is
available if the fan-out becomes a bottleneck in production.

**LLM cost per query** — Gemini Flash-Lite (mechanical routing, tool dispatch) +
Gemini Flash (synthesis) with Grok fallover. A typical agent turn uses 3–6 tool calls
and 2–4k tokens; at Gemini Flash pricing this is < $0.01/turn. The adapter enforces
an 8-iteration / ~16k-token cap per turn to bound worst-case cost.

---

## Isolation & erasure

**RLS enforcement** — Every user-data table has a Row-Level Security policy keyed on
`current_setting('app.user_id')`. The FastAPI dependency `get_rls_session` sets this
GUC at the start of each request and resets it in a `finally` block; a pool event
hook (`checkout`) resets it again as defence in depth, so a pooled connection can
never leak a previous user's identity.

**Right-to-erasure purge path** (implemented in Phase 6) — `DELETE /users/me/erasure`
hard-deletes all 9 user-scoped tables (in FK-safe order: corrections, memory,
user_settings, goals, forecasts, anomalies, subscriptions, transactions) then the
`users` row, purges Redis session keys with `SCAN`/`DEL`, and writes an
`erasure_audit` record in a separate transaction. The audit record is retained
indefinitely for operator compliance review; it carries no PII.

**Model-unlearning limitation** — After erasure, the user's label corrections may
still be encoded in the champion model's weights if a retrain occurred. Full machine
unlearning requires a complete retrain on data excluding the user's examples; this is
not currently automated. Documented in `SECURITY.md §Model Unlearning Limitation`.

---

## ML lifecycle

**Champion/challenger gate** — The trainer (heavy image, `training` compose profile)
exports a new ONNX artifact and calls `training/gate_holdout.py` against the frozen
holdout set. Promotion requires `challenger.macro_f1 > champion.macro_f1` (strict
`>`, not `>=`) AND an operator approval via the `/retrain/{run_id}/promote` endpoint.
A challenger that ties or loses is blocked; the champion stays.

**Drift detection signals** — The light worker evaluates four signals on each
recompute cycle: (1) mean model confidence below `mean_confidence_min` (0.70);
(2) correction rate above `correction_rate_max` (0.20); (3) PSI above `psi_max`
(0.20) for the `category` distribution; (4) new-merchant rate above
`new_merchant_rate_max` (0.15). Any signal firing triggers a Slack webhook and
enqueues an RQ `training` job.

**Retrain cadence** — Retrains are event-driven (drift signal fires) plus a monthly
scheduled run regardless. The `training` RQ queue is consumed by the trainer
container only when the `training` compose profile is active; the default stack never
starts the trainer.

**Ops signals only** — Slack webhook payloads carry gate name, threshold, measured
value, and run ID. No user-level data (transaction amounts, categories, identifiers)
ever appears in a webhook payload (constitution Art. II).
