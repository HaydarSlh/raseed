"""LLM adapter: single boundary over Gemini Flash-Lite/Flash with Grok failover. All hosted-model calls route here; no other module imports a provider SDK (constitution Art. IV/V, FR-013)."""

from __future__ import annotations

import abc
from pathlib import Path
from typing import Literal

import structlog

from app.core.exceptions import UpstreamError
from app.core.observability import span, with_retry

log = structlog.get_logger(__name__)

Tier = Literal["mechanical", "synthesis"]

PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"

# Both tiers use gemini-2.5-flash: it follows the JSON-action protocol reliably,
# whereas 2.5-flash-lite intermittently returns empty text
# (finish_reason=UNEXPECTED_TOOL_CALL), which wastes retries and free-tier quota.
_GEMINI_MODELS: dict[Tier, str] = {
    "mechanical": "gemini-2.5-flash",
    "synthesis": "gemini-2.5-flash",
}


class Completion:
    __slots__ = ("text", "provider", "model")

    def __init__(self, text: str, *, provider: str, model: str) -> None:
        self.text = text
        self.provider = provider
        self.model = model


class BaseLLM(abc.ABC):
    @abc.abstractmethod
    async def complete(self, prompt: str, *, tier: Tier = "mechanical") -> Completion: ...


class FakeLLM(BaseLLM):
    """Test/local double — returns deterministic text without hitting any API."""

    async def complete(self, prompt: str, *, tier: Tier = "mechanical") -> Completion:
        return Completion(f"[FakeLLM:{tier}] prompt={prompt[:40]!r}", provider="fake", model="fake")


class GeminiGrokLLM(BaseLLM):
    """Production adapter: Gemini Flash-Lite/Flash with Grok HTTP failover.

    All calls use `with_retry` (bounded backoff, 4xx not retried). Prompts are
    loaded from `backend/prompts/`; no inline strings (Art. IV). Only
    summaries/aggregates cross this boundary; user identifiers never do (Art. II).
    """

    def __init__(self, gemini_api_key: str, grok_api_key: str) -> None:
        self._gemini_key = gemini_api_key
        self._grok_key = grok_api_key

    async def complete(self, prompt: str, *, tier: Tier = "mechanical") -> Completion:
        model_name = _GEMINI_MODELS[tier]
        try:
            return await self._call_gemini(prompt, model_name)
        except Exception as exc:
            log.warning("llm.gemini.failed", error=str(exc), tier=tier, model=model_name)
            return await self._call_grok(prompt, tier=tier)

    async def _call_gemini(self, prompt: str, model_name: str) -> Completion:
        import google.genai as genai  # imported here so serving image without key won't fail at import
        from google.genai import types

        # Disable Gemini 2.5 "thinking": the agent runs its own ReAct loop, and
        # thinking tokens can consume the response budget and return an empty
        # `.text`. thinking_budget=0 makes mechanical/synthesis calls reliable.
        config = types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        )
        async for attempt in with_retry(max_attempts=3, timeout=30.0):
            with attempt:
                with span("llm.gemini", model=model_name):
                    client = genai.Client(api_key=self._gemini_key)
                    response = await client.aio.models.generate_content(
                        model=model_name, contents=prompt, config=config
                    )
                    text = response.text or ""
                    # gemini-2.5-flash-lite occasionally returns empty text with
                    # finish_reason=UNEXPECTED_TOOL_CALL. Treat empty as a transient
                    # failure so with_retry re-attempts (not a 4xx → retryable).
                    if not text.strip():
                        raise UpstreamError(f"Gemini returned empty text ({model_name})")
                    return Completion(text, provider="gemini", model=model_name)
        raise UpstreamError("Gemini retries exhausted")  # pragma: no cover

    async def _call_grok(self, prompt: str, *, tier: Tier) -> Completion:
        import httpx

        # Groq (api.groq.com) failover — the gsk_ key prefix is a Groq key, not
        # an xAI/Grok key. Groq serves Llama models via an OpenAI-compatible API.
        groq_model = "llama-3.1-8b-instant" if tier == "mechanical" else "llama-3.3-70b-versatile"
        async for attempt in with_retry(max_attempts=2, timeout=30.0):
            with attempt:
                with span("llm.groq", model=groq_model):
                    async with httpx.AsyncClient() as client:
                        response = await client.post(
                            "https://api.groq.com/openai/v1/chat/completions",
                            headers={"Authorization": f"Bearer {self._grok_key}"},
                            json={"model": groq_model, "messages": [{"role": "user", "content": prompt}]},
                            timeout=30.0,
                        )
                        if 400 <= response.status_code < 500:
                            body = response.text[:300]
                            log.warning(
                                "llm.groq.4xx",
                                status=response.status_code,
                                model=groq_model,
                                body=body,
                            )
                            raise UpstreamError(f"Groq {response.status_code}: {body}")
                        response.raise_for_status()
                        data = response.json()
                        text = data["choices"][0]["message"]["content"]
                        return Completion(text, provider="groq", model=groq_model)
        raise UpstreamError("Groq retries exhausted")  # pragma: no cover


def build_llm(*, gemini_api_key: str = "", grok_api_key: str = "", use_fake: bool = False) -> BaseLLM:
    """Factory: returns FakeLLM when no keys are configured or use_fake=True."""
    if use_fake or (not gemini_api_key and not grok_api_key):
        log.info("llm.using_fake")
        return FakeLLM()
    return GeminiGrokLLM(gemini_api_key=gemini_api_key, grok_api_key=grok_api_key)


_adapter: BaseLLM | None = None


def init_llm(adapter: BaseLLM) -> None:
    global _adapter
    _adapter = adapter


def get_llm() -> BaseLLM:
    assert _adapter is not None, "LLM adapter not initialised — call init_llm() in lifespan"
    return _adapter
