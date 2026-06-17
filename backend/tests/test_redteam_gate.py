"""CI Gate #5 (red-team probe suite) + Gate #6 Part 1 (PII pipeline check).

Stack-independent: no DB, no Redis, no LLM API call.
Every 'refused' probe must raise RailRefusal; every 'allowed' probe must not.
PII string must be absent from the redact() output.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.exceptions import RailRefusal
from app.services.agent.rails import check_input, redact

_PROBES_PATH = Path(__file__).parent / "fixtures" / "redteam_probes.json"


def _load_probes() -> list[dict]:
    return json.loads(_PROBES_PATH.read_text(encoding="utf-8"))


# ── Gate #5: red-team probe suite ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_gate5_all_refused_probes_raise_rail_refusal() -> None:
    """Every probe with expected='refused' must raise RailRefusal. Zero non-refusals allowed."""
    probes = [p for p in _load_probes() if p["expected"] == "refused"]
    assert len(probes) >= 10, "Minimum 10 refused probes required in the suite"

    failures: list[str] = []
    for probe in probes:
        try:
            await check_input(probe["payload"])
            failures.append(f"{probe['id']} ({probe['category']}): did NOT raise RailRefusal")
        except RailRefusal:
            pass  # expected

    assert not failures, "Gate #5 FAILED — probes not refused:\n" + "\n".join(failures)


@pytest.mark.asyncio
async def test_gate5_allowed_probes_pass_through() -> None:
    """Probes marked 'allowed' must not raise RailRefusal."""
    probes = [p for p in _load_probes() if p["expected"] == "allowed"]
    for probe in probes:
        result = await check_input(probe["payload"])
        assert isinstance(result, str), f"{probe['id']}: check_input returned non-string"


# ── Gate #6 Part 1: PII pipeline check ────────────────────────────────────────

def test_gate6_part1_card_number_redacted_before_llm() -> None:
    """A message containing a test PAN must have the raw number removed by redact()."""
    raw = "Please help, my card number is 4111111111111111 and I'm worried."
    result = redact(raw)
    assert "4111111111111111" not in result, "Raw PAN reached output — redaction failed"
    assert "[REDACTED-CARD]" in result


def test_gate6_part1_api_key_redacted_before_llm() -> None:
    """A message containing a fake API key must have it removed by redact()."""
    raw = "I accidentally included my key sk-testkey12345678 in my message."
    result = redact(raw)
    assert "sk-testkey12345678" not in result, "Raw API key reached output — redaction failed"
    assert "[REDACTED-KEY]" in result


def test_gate6_part1_combined_pii_all_redacted() -> None:
    """Multiple PII types in one message must all be replaced."""
    raw = "Call me at 07700900123 or email test@example.com, card 4111111111111111"
    result = redact(raw)
    assert "07700900123" not in result
    assert "test@example.com" not in result
    assert "4111111111111111" not in result
