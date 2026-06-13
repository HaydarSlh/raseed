"""LLM adapter: single boundary over Gemini Flash-Lite/Flash with Grok failover; timeouts + tenacity retry, 4xx never retried (constitution Art. V). Stub in Phase 0."""

from __future__ import annotations

# Phase 4 implements the two-tier routing (Flash-Lite mechanical / Flash synthesis)
# and Gemini -> Grok failover inside this single adapter. Prompts come from
# `backend/prompts/` files — never inline strings (Art. IV). Data minimization:
# only summaries/aggregates cross this boundary; identifiers never do (Art. II).
