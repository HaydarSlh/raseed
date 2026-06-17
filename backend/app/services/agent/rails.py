"""No-op safety rails — call sites exist for Phase 6 to fill (FR-022, constitution Art. I)."""

from __future__ import annotations


async def check_input(message: str) -> str:
    """Input content check (no-op this phase)."""
    return message


async def check_output(text: str) -> str:
    """Output content check (no-op this phase)."""
    return text


def redact(text: str) -> str:
    """PII redaction before LLM egress (no-op this phase)."""
    return text
