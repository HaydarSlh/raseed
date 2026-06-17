"""Integration test: affordability question yields multi-source answer within iteration cap (SC-005/008)."""

from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock

import pytest

pytestmark = pytest.mark.asyncio


async def test_affordability_uses_agent_route() -> None:
    """Affordability question must route to agent (not deterministic)."""
    from app.services.agent.router import route

    mock_session = AsyncMock()
    decision = await route(
        "Can I afford a £1,200 holiday in August without missing my savings goal?",
        session=mock_session,
        user_id=uuid.uuid4(),
    )
    assert decision.route == "agent"
    assert decision.answer is None


async def test_agent_stays_bounded() -> None:
    """Agent loop must stop at max_iterations and return bounded=True when thrashing."""
    from app.infra.llm import Completion, FakeLLM
    from app.services.agent.loop import run_agent

    call_count = 0

    async def always_tool(prompt: str, *, tier: str = "mechanical") -> Completion:
        nonlocal call_count
        call_count += 1
        if call_count > 20:
            return Completion(json.dumps({"final": "done", "citations": []}), provider="fake", model="fake")
        return Completion(json.dumps({"tool": "get_subscriptions", "args": {}}), provider="fake", model="fake")

    llm = FakeLLM()
    llm.complete = always_tool  # type: ignore[method-assign]

    import app.services.agent.tools.reads  # ensure registered  # noqa: F401

    result = await run_agent(
        "complex question",
        llm=llm,
        context=[],
        max_iterations=8,
        token_budget=999999,
    )
    assert result.bounded is True
    assert result.iterations <= 8
