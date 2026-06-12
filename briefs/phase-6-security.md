# Phase 6 — Security & compliance hardening

## Intent
The conversation surface and the data boundary withstand deliberate attack,
and a user can truly erase themselves.

## In scope (deliverables)
- Fill the Phase-4 rails hook points: input/output rails in-process —
  prompt-injection & jailbreak heuristics, on-domain topical control,
  no-licensed-advice output rule.
- PII redaction implemented at the stubbed call site: runs before logs, traces,
  and LLM calls; the fake-API-key test proves a secret pasted into chat never
  appears unredacted anywhere.
- Red-team suite as CI gate #5: injection probes, cross-user extraction
  attempts, system-prompt extraction — every attempt must be refused.
- Per-user rate limiting, tightest on the LLM-triggered write tools
  (add_transaction, reclassify, set_goal).
- Right-to-erasure path: purges Postgres rows, user-scoped pgvector memory,
  and Redis sessions; audit-logged. (No blob component — user files are never
  persisted; MinIO holds only model artifacts.) SECURITY.md documents the
  model-unlearning limitation for corrections already trained on.
- Vault hardening pass: `grep -r "sk-"` clean; service-role/privileged paths
  reviewed.

## Acceptance criteria
- CI gates #5 (red-team) and #6 (redaction) green.
- Erasure verified by a test that searches EVERY store after deletion.
- Rate-limit test on add_transaction passes.

## Notes for /plan
Rails are in-process (NeMo sidecar = documented future work). Rails must not
add an external service dependency to the chat path.
