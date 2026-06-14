# Contract: LLM Adapter (single model gateway)

`infra/llm.py` is the ONLY code path that calls a hosted model (Art. IV/V). No
service, repository, or router calls a provider SDK directly.

## Interface

A single async boundary, e.g.:

```
async def complete(prompt: Prompt, *, tier: "mechanical" | "synthesis") -> Completion
```

- `tier="mechanical"` → Gemini Flash-Lite; `tier="synthesis"` → Gemini Flash.
- Prompts are loaded from `backend/prompts/` files — never inline strings.

## Behavioral contract

1. **Single entry point**: all hosted-model calls go through this adapter; a
   repo-wide check finds no other direct hosted-model call. *(FR-013, SC-007)*
2. **Failover order**: on Gemini failure, fail over to Grok within the adapter; if
   all providers fail, raise a structured `UpstreamError`. *(FR-013, edge: outage)*
3. **Timeout + retry**: every call has a timeout and tenacity backoff; **4xx
   responses are NOT retried**; retries are bounded. *(FR-013, Art. V)*
4. **Structured errors**: failures surface as domain errors, never raw traces.
   *(FR-012)*
5. **Fake double**: a `FakeLLM` implements the same interface and is injected in
   tests and whenever no provider key is configured — tests never hit a live model.
   *(FR-014)*
6. **Data minimization (forward-looking)**: only summaries/aggregates may cross this
   boundary; identifiers never do. Enforced when real call sites land (Art. II); no
   user data crosses in Phase 1 (no call sites yet).
