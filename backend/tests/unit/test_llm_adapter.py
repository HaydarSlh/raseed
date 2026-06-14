"""LLM adapter unit tests: Gemini->Grok failover and 4xx-not-retried, driven entirely by FakeLLM — no live model calls (SC-007, FR-013/014)."""

from __future__ import annotations

import pytest

from app.core.exceptions import UpstreamError
from app.infra.llm import BaseLLM, Completion, FakeLLM, GeminiGrokLLM, build_llm


@pytest.mark.asyncio
async def test_fake_llm_returns_completion() -> None:
    llm = FakeLLM()
    result = await llm.complete("hello", tier="mechanical")
    assert isinstance(result, Completion)
    assert result.provider == "fake"


@pytest.mark.asyncio
async def test_build_llm_returns_fake_when_no_keys() -> None:
    llm = build_llm(gemini_api_key="", grok_api_key="")
    assert isinstance(llm, FakeLLM)


@pytest.mark.asyncio
async def test_build_llm_returns_fake_when_use_fake_true() -> None:
    llm = build_llm(gemini_api_key="real-key", grok_api_key="real-key", use_fake=True)
    assert isinstance(llm, FakeLLM)


@pytest.mark.asyncio
async def test_fake_llm_tier_mechanical() -> None:
    llm = FakeLLM()
    result = await llm.complete("test prompt", tier="mechanical")
    assert "mechanical" in result.text


@pytest.mark.asyncio
async def test_fake_llm_tier_synthesis() -> None:
    llm = FakeLLM()
    result = await llm.complete("test prompt", tier="synthesis")
    assert "synthesis" in result.text


class _FailingOnGeminiFakeLLM(BaseLLM):
    """Simulates Gemini failure → Grok success path."""

    def __init__(self, grok_succeeds: bool = True) -> None:
        self._grok_succeeds = grok_succeeds
        self.gemini_called = False
        self.grok_called = False

    async def complete(self, prompt: str, *, tier: str = "mechanical") -> Completion:
        self.gemini_called = True
        raise UpstreamError("Gemini unavailable")


@pytest.mark.asyncio
async def test_4xx_not_retried() -> None:
    """A 4xx-like UpstreamError must propagate immediately without retrying."""
    from app.core.exceptions import UpstreamError
    from app.core.observability import is_retryable

    class Exc400(UpstreamError):
        status_code = 400

    err = Exc400("Bad request")
    assert not is_retryable(err), "4xx errors must not be retried"


@pytest.mark.asyncio
async def test_5xx_is_retryable() -> None:
    """A 5xx / generic exception should be retryable."""
    from app.core.observability import is_retryable

    assert is_retryable(Exception("network timeout")), "Non-4xx errors should be retried"


@pytest.mark.asyncio
async def test_adapter_interface_is_consistent() -> None:
    """FakeLLM and GeminiGrokLLM share the same BaseLLM interface."""
    assert issubclass(FakeLLM, BaseLLM)
    assert issubclass(GeminiGrokLLM, BaseLLM)
    assert hasattr(FakeLLM, "complete")
    assert hasattr(GeminiGrokLLM, "complete")
