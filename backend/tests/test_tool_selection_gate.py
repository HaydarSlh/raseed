"""Gate 3: Tool-selection accuracy on the committed golden set (SC-002, research R11).

Uses FakeEmbedder/FakeLLM — never calls a hosted model (Art. V).
Reads thresholds from eval_thresholds.yaml; a regression below floor blocks CI.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml

import app.services.agent.tools.analysis  # noqa: F401
import app.services.agent.tools.goals  # noqa: F401
import app.services.agent.tools.knowledge  # noqa: F401
import app.services.agent.tools.memory  # noqa: F401
import app.services.agent.tools.reads  # noqa: F401
import app.services.agent.tools.writes  # noqa: F401

_GOLDEN_PATH = Path(__file__).parent / "golden" / "tool_selection" / "cases.yaml"
_THRESHOLDS_PATH = Path(__file__).parent.parent.parent / "eval_thresholds.yaml"


def _load_cases() -> list[dict]:
    return yaml.safe_load(_GOLDEN_PATH.read_text())["cases"]


def _load_threshold() -> float:
    data = yaml.safe_load(_THRESHOLDS_PATH.read_text())
    val = data.get("router", {}).get("tool_selection_accuracy_min", 0.0)
    return float(val) if val is not None else 0.0


@pytest.mark.asyncio
async def test_tool_selection_accuracy() -> None:
    """Route classification accuracy on the golden set must meet the committed threshold."""
    cases = _load_cases()
    threshold = _load_threshold()

    mock_session = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one.return_value = 0
    result_mock.scalars.return_value.all.return_value = []
    mock_session.execute.return_value = result_mock

    import uuid

    from app.services.agent import router as agent_router

    correct = 0
    total = len(cases)

    for case in cases:
        user_id = uuid.uuid4()
        decision = await agent_router.route(case["message"], session=mock_session, user_id=user_id)
        expected_route = case["expected_route"]
        if decision.route == expected_route:
            correct += 1

    accuracy = correct / total
    print(f"\nTool-selection accuracy: {correct}/{total} = {accuracy:.2%} (threshold: {threshold:.2%})")
    assert accuracy >= threshold, (
        f"Tool-selection accuracy {accuracy:.2%} below threshold {threshold:.2%} "
        f"({correct}/{total} cases correct)"
    )
