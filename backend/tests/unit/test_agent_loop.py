"""Unit tests: agent loop caps, allowlist enforcement, structured error handling (FR-006/007/010)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest
from pydantic import BaseModel

from app.infra.llm import Completion, FakeLLM
from app.services.agent.loop import run_agent
from app.services.agent.tools.registry import dispatch, register_tool


class EmptyInput(BaseModel):
    pass


# ── Helpers ───────────────────────────────────────────────────────────────────

def _llm_answering(answer: str = "done") -> FakeLLM:
    """FakeLLM that immediately returns a final answer JSON."""
    llm = FakeLLM()
    llm.complete = AsyncMock(  # type: ignore[method-assign]
        return_value=Completion(
            json.dumps({"final": answer, "citations": []}),
            provider="fake",
            model="fake",
        )
    )
    return llm


def _llm_thrashing(max_calls: int = 20) -> FakeLLM:
    """FakeLLM that always calls a dummy tool, forcing the cap to be hit."""
    llm = FakeLLM()
    call_count = 0

    async def _complete(prompt: str, *, tier: str = "mechanical") -> Completion:
        nonlocal call_count
        call_count += 1
        if call_count > max_calls:
            return Completion(
                json.dumps({"final": "cap hit", "citations": []}),
                provider="fake",
                model="fake",
            )
        return Completion(
            json.dumps({"tool": "dummy_tool", "args": {}}),
            provider="fake",
            model="fake",
        )

    llm.complete = AsyncMock(side_effect=_complete)  # type: ignore[method-assign]
    return llm


# ── Tests ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_loop_returns_final_answer() -> None:
    llm = _llm_answering("Hello from agent")
    result = await run_agent("test question", llm=llm, context=[])
    assert result.answer == "Hello from agent"
    assert result.bounded is False
    assert result.iterations == 1


@pytest.mark.asyncio
async def test_loop_caps_at_max_iterations() -> None:
    """Loop must stop at max_iterations and set bounded=True (FR-006, SC-008)."""
    # Register a dummy tool so dispatch succeeds
    register_tool("dummy_tool", EmptyInput, AsyncMock(return_value={"ok": True}))

    llm = _llm_thrashing(max_calls=50)
    result = await run_agent(
        "keep calling tools",
        llm=llm,
        context=[],
        max_iterations=8,
        token_budget=999999,
    )
    assert result.bounded is True
    assert result.iterations <= 8


@pytest.mark.asyncio
async def test_non_allowlisted_tool_returns_structured_error() -> None:
    """A tool name not in the registry must return a structured error, never raise (FR-007)."""
    result = await dispatch("totally_unknown_tool", {})
    assert "error" in result
    assert "totally_unknown_tool" in result["error"].lower() or "unknown" in result["error"].lower()


@pytest.mark.asyncio
async def test_invalid_args_return_structured_error() -> None:
    """Malformed args (schema violation) must return a structured error (FR-008)."""
    from pydantic import BaseModel

    class StrictInput(BaseModel):
        amount: float

    register_tool("strict_tool", StrictInput, AsyncMock(return_value={"ok": True}))

    result = await dispatch("strict_tool", {"amount": "not_a_number"})
    assert "error" in result


@pytest.mark.asyncio
async def test_tool_exception_returns_structured_error() -> None:
    """A tool that raises must yield a structured error, not propagate the exception (FR-010)."""

    async def _exploding(**_kwargs: object) -> dict:
        raise RuntimeError("boom")

    register_tool("exploding_tool", EmptyInput, _exploding)
    result = await dispatch("exploding_tool", {})
    assert "error" in result
    assert "exploding_tool" in result["error"]


@pytest.mark.asyncio
async def test_token_budget_triggers_bounded() -> None:
    """When token budget is too small to fit even the first prompt, bounded=True (FR-006)."""
    llm = _llm_thrashing()
    result = await run_agent(
        "test",
        llm=llm,
        context=[],
        max_iterations=8,
        token_budget=1,  # impossibly small
    )
    assert result.bounded is True
