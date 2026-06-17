"""Deterministic router: resolves enumerable turns with exact SQL, no LLM (FR-003/005, SC-001/006)."""

from __future__ import annotations

import re
import uuid
from datetime import date, timedelta

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.chat import RouterDecision

log = structlog.get_logger(__name__)

# Intent patterns — high-precision, ordered by specificity
_BALANCE_PATTERNS = [
    re.compile(r"\b(balance|how much (?:do i have|money|have i got|is in my account))\b", re.I),
    re.compile(r"\bwhat.{0,10}(balance|left|remaining)\b", re.I),
]
_SUBSCRIPTION_PATTERNS = [
    re.compile(r"\b(subscriptions?|recurring|subscribed to|monthly charges?)\b", re.I),
]
_CATEGORY_PATTERNS = [
    re.compile(r"\b(how much (?:did i|have i|do i) (?:spend|spent|pay|paid)(?: on)?)\s+([a-z ]{2,40})\b", re.I),
    re.compile(r"\b(spending|spend|spent|total)(?: on)?\s+([a-z ]{2,40})\b", re.I),
]


def _match_category(message: str) -> str | None:
    for pat in _CATEGORY_PATTERNS:
        m = pat.search(message)
        if m:
            return m.group(2).strip().rstrip("?").strip()
    return None


async def route(
    message: str,
    *,
    session: AsyncSession,
    user_id: uuid.UUID,
) -> RouterDecision:
    """Classify the message; if enumerable, run the SQL query and return the answer inline."""
    msg = message.strip()

    # ── Balance query ─────────────────────────────────────────────────────────
    if any(p.search(msg) for p in _BALANCE_PATTERNS):
        from sqlalchemy import func, select

        from app.domain.transaction import Transaction

        result = await session.execute(
            select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                Transaction.user_id == user_id
            )
        )
        balance = float(result.scalar_one() or 0)
        answer = f"Your current balance is £{balance:,.2f}."
        log.info("router.deterministic", intent="balance", user_id=str(user_id))
        return RouterDecision(route="deterministic", answer=answer)

    # ── Subscription query ────────────────────────────────────────────────────
    if any(p.search(msg) for p in _SUBSCRIPTION_PATTERNS):
        from sqlalchemy import select

        from app.domain.analytics import Subscription

        sub_result = await session.execute(
            select(Subscription).where(Subscription.user_id == user_id)
        )
        subs = list(sub_result.scalars().all())
        if not subs:
            answer = "I don't see any recurring subscriptions in your recent transactions."
        else:
            lines = [f"- {s.merchant}: £{float(s.typical_amount):,.2f}/{s.cadence.value}" for s in subs]
            answer = "Your subscriptions:\n" + "\n".join(lines)
        log.info("router.deterministic", intent="subscriptions", user_id=str(user_id))
        return RouterDecision(route="deterministic", answer=answer)

    # ── Category total query ──────────────────────────────────────────────────
    category = _match_category(msg)
    if category:
        from sqlalchemy import func, select

        from app.domain.transaction import Transaction

        # Default to last 30 days
        start = date.today() - timedelta(days=30)
        result = await session.execute(
            select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                Transaction.user_id == user_id,
                Transaction.category.ilike(f"%{category}%"),
                Transaction.occurred_at >= start,
            )
        )
        total = abs(float(result.scalar_one() or 0))
        answer = f"You spent £{total:,.2f} on {category} in the last 30 days."
        log.info("router.deterministic", intent="category_total", category=category, user_id=str(user_id))
        return RouterDecision(route="deterministic", answer=answer)

    # ── Send to agent ─────────────────────────────────────────────────────────
    log.info("router.agent", user_id=str(user_id))
    return RouterDecision(route="agent", answer=None)
