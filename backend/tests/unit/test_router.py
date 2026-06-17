"""Unit tests: deterministic router classifies enumerable turns correctly (FR-003/005, SC-001/006)."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.agent.router import (
    _BALANCE_PATTERNS,
    _SUBSCRIPTION_PATTERNS,
    _match_category,
    route,
)

# ── Pattern-level unit tests (no DB needed) ───────────────────────────────────

@pytest.mark.parametrize("msg", [
    "What's my balance?",
    "How much money do I have?",
    "what is my balance",
    "how much do I have left",
])
def test_balance_patterns_match(msg: str) -> None:
    assert any(p.search(msg) for p in _BALANCE_PATTERNS), f"Expected balance match for: {msg!r}"


@pytest.mark.parametrize("msg", [
    "What are my subscriptions?",
    "Show me my recurring charges",
    "what am I subscribed to",
    "list my monthly charges",
])
def test_subscription_patterns_match(msg: str) -> None:
    assert any(p.search(msg) for p in _SUBSCRIPTION_PATTERNS), f"Expected subscription match for: {msg!r}"


@pytest.mark.parametrize("msg,expected_category", [
    ("How much did I spend on groceries last month?", "groceries"),
    ("how much did i spend on dining", "dining"),
    ("total spending on transport", "transport"),
])
def test_category_pattern_extracts_category(msg: str, expected_category: str) -> None:
    cat = _match_category(msg)
    assert cat is not None, f"Expected category match for: {msg!r}"
    assert expected_category in cat.lower()


@pytest.mark.parametrize("msg", [
    "Can I afford a holiday?",
    "Should I invest in stocks?",
    "What's the best credit card?",
    "How do I save money on groceries?",
])
def test_agent_turn_not_matched(msg: str) -> None:
    assert not any(p.search(msg) for p in _BALANCE_PATTERNS)
    assert not any(p.search(msg) for p in _SUBSCRIPTION_PATTERNS)
    assert _match_category(msg) is None


# ── Route function tests (mocked session) ─────────────────────────────────────

@pytest.fixture
def mock_session() -> AsyncMock:
    session = AsyncMock()
    # Default scalar returns 0
    result = MagicMock()
    result.scalar_one.return_value = 0
    result.scalars.return_value.all.return_value = []
    session.execute.return_value = result
    return session


@pytest.mark.asyncio
async def test_route_balance_is_deterministic(mock_session: AsyncMock) -> None:
    result = mock_session.execute.return_value
    result.scalar_one.return_value = 1234.56
    decision = await route("What's my balance?", session=mock_session, user_id=uuid.uuid4())
    assert decision.route == "deterministic"
    assert "1,234.56" in (decision.answer or "")


@pytest.mark.asyncio
async def test_route_subscriptions_is_deterministic(mock_session: AsyncMock) -> None:
    decision = await route("Show me my subscriptions", session=mock_session, user_id=uuid.uuid4())
    assert decision.route == "deterministic"


@pytest.mark.asyncio
async def test_route_complex_query_is_agent(mock_session: AsyncMock) -> None:
    decision = await route(
        "Can I afford a £1,200 holiday in August without missing my savings goal?",
        session=mock_session,
        user_id=uuid.uuid4(),
    )
    assert decision.route == "agent"
    assert decision.answer is None
