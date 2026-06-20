"""Unit tests: agent loop caps, allowlist enforcement, structured error handling (FR-006/007/010)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from app.infra.llm import Completion, FakeLLM
from app.services.agent.loop import run_agent
from app.services.agent.tools.registry import dispatch, register_tool


class EmptyInput(BaseModel):
    pass


# Session/user_id are injected into every tool call by the loop; the dummy tools
# here ignore them, so a stub session and a throwaway user_id suffice.
_FAKE_SESSION = MagicMock()
_FAKE_USER_ID = uuid.uuid4()


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
    result = await run_agent(
        "test question", llm=llm, context=[], session=_FAKE_SESSION, user_id=_FAKE_USER_ID
    )
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
        session=_FAKE_SESSION,
        user_id=_FAKE_USER_ID,
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
async def test_session_and_user_id_are_injected_into_tools() -> None:
    """Regression: the loop must inject the RLS session + user_id into tool calls.

    Previously run_agent never threaded session/user_id through dispatch, so every
    DB-backed tool short-circuited with "Session context not available" and the
    agent fell back to generic advice. This drives query_transactions end-to-end
    and asserts it actually queried the injected session.
    """
    import app.services.agent.tools.reads  # ensure query_transactions is registered  # noqa: F401

    # Two fake rows shaped like Transaction (tool reads occurred_at/amount/category).
    row_a = MagicMock(occurred_at=datetime(2026, 1, 5), amount=-12.50, category="coffee")
    row_b = MagicMock(occurred_at=datetime(2026, 1, 6), amount=-40.00, category="coffee")
    # `await session.execute(q)` must be async, but the returned result object is used
    # synchronously (`.scalars().all()`), so it has to be a plain MagicMock.
    exec_result = MagicMock()
    exec_result.scalars.return_value.all.return_value = [row_a, row_b]
    session = AsyncMock()
    session.execute = AsyncMock(return_value=exec_result)

    # FakeLLM: first turn calls the tool, second turn returns the tool's count as final.
    seen_tool_result: dict = {}
    call_count = 0

    async def _complete(prompt: str, *, tier: str = "mechanical") -> Completion:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return Completion(
                json.dumps({"tool": "query_transactions", "args": {"category": "coffee"}}),
                provider="fake",
                model="fake",
            )
        # The tool result is appended to the prompt; capture it for assertions.
        seen_tool_result["prompt"] = prompt
        return Completion(
            json.dumps({"final": "done", "citations": []}), provider="fake", model="fake"
        )

    llm = FakeLLM()
    llm.complete = AsyncMock(side_effect=_complete)  # type: ignore[method-assign]

    user_id = uuid.uuid4()
    result = await run_agent(
        "what redundant spending do I have?",
        llm=llm,
        context=[],
        session=session,
        user_id=user_id,
    )

    # The tool executed against the injected session (not the None-guard error path).
    session.execute.assert_awaited()
    follow_up_prompt = seen_tool_result.get("prompt", "")
    assert "Session context not available" not in follow_up_prompt
    assert '"count": 2' in follow_up_prompt  # both fake rows flowed through
    assert result.answer == "done"


@pytest.mark.asyncio
async def test_token_budget_triggers_bounded() -> None:
    """When token budget is too small to fit even the first prompt, bounded=True (FR-006)."""
    llm = _llm_thrashing()
    result = await run_agent(
        "test",
        llm=llm,
        context=[],
        session=_FAKE_SESSION,
        user_id=_FAKE_USER_ID,
        max_iterations=8,
        token_budget=1,  # impossibly small
    )
    assert result.bounded is True


@pytest.mark.asyncio
async def test_unparseable_output_after_tool_preserves_citations() -> None:
    """When the LLM emits prose (not JSON) after a tool call, the loop must:
    1. attempt a synthesis pass, and
    2. include citations collected from the prior tool result.
    """
    import app.services.agent.tools.knowledge  # noqa: F401  (register search_financial_knowledge)

    # Patch the retrieval pipeline so the tool returns a known passage with a citation.
    mock_retrieve = AsyncMock(return_value={
        "passages": [
            {"passage_id": "p1", "document_slug": "budgeting", "heading_path": "Budgeting > Step 1", "content": "Track spending"},
        ],
        "citations": [{"document_slug": "budgeting", "heading_path": "Budgeting > Step 1"}],
    })

    with (
        patch("app.services.agent.tools.knowledge.get_embedder", return_value=MagicMock()),
        patch("app.services.agent.tools.knowledge.get_session_factory"),
        patch("app.services.agent.tools.knowledge.retrieve", mock_retrieve),
    ):
        call_count = 0

        async def _complete(prompt: str, *, tier: str = "mechanical") -> Completion:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call: emit a tool call
                return Completion(
                    json.dumps({"tool": "search_financial_knowledge", "args": {"query": "budgeting"}}),
                    provider="fake",
                    model="fake",
                )
            if call_count == 2:
                # Second call: prose instead of JSON (simulates the bug)
                return Completion(
                    "I'm having trouble accessing my knowledge base right now. Based on your balance...",
                    provider="fake",
                    model="fake",
                )
            # Third call (synthesis): clean final answer
            return Completion(
                json.dumps({"final": "Here is how to budget: track your spending.", "citations": []}),
                provider="fake",
                model="fake",
            )

        llm = FakeLLM()
        llm.complete = AsyncMock(side_effect=_complete)  # type: ignore[method-assign]

        result = await run_agent(
            "how do I budget?",
            llm=llm,
            context=[],
            session=_FAKE_SESSION,
            user_id=_FAKE_USER_ID,
        )

    # The synthesis pass succeeded → clean answer, and citations from the tool are preserved.
    assert "track your spending" in result.answer.lower() or "budget" in result.answer.lower()
    assert len(result.citations) == 1
    assert result.citations[0]["document_slug"] == "budgeting"
