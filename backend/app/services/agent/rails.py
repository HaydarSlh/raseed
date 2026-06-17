"""In-process safety rails: PII redaction, input/output content checks (Phase 6, FR-001/002/003/004)."""

from __future__ import annotations

import re

import structlog

from app.core.exceptions import RailRefusal

log = structlog.get_logger(__name__)

# ── PII redaction patterns (compiled once at module load) ─────────────────────

_PAN = re.compile(r"\b(?:\d[ \-]?){12,18}\d\b")          # 13-19 digit card numbers
_IBAN = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{4,30}\b")   # IBAN
_UK_PHONE = re.compile(r"(?:\+44\s?|0)(?:\d[\s\-]?){9,10}")
_EMAIL = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_API_KEY = re.compile(r"sk-[A-Za-z0-9]{8,}")              # OpenAI/Anthropic style
_GEMINI_KEY = re.compile(r"AIza[A-Za-z0-9\-_]{35}")       # Google API key

_REDACTION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (_PAN, "[REDACTED-CARD]"),
    (_IBAN, "[REDACTED-IBAN]"),
    (_UK_PHONE, "[REDACTED-PHONE]"),
    (_EMAIL, "[REDACTED-EMAIL]"),
    (_API_KEY, "[REDACTED-KEY]"),
    (_GEMINI_KEY, "[REDACTED-KEY]"),
]

# ── Input rail keyword sets ───────────────────────────────────────────────────

_INJECTION_PHRASES = [
    "ignore all previous instructions",
    "ignore previous instructions",
    "disregard your instructions",
    "forget your instructions",
    "override your instructions",
    "system prompt",
    "reveal your prompt",
    "show your prompt",
    "print your prompt",
]

_JAILBREAK_PHRASES = [
    "act as ",
    "pretend you are",
    "pretend to be",
    "you are now",
    " dan ",
    "do anything now",
    "jailbreak",
    "unrestricted mode",
    "no restrictions",
    "developer mode",
]

_EXTRACTION_PHRASES = [
    "what are your instructions",
    "show me your system message",
    "reveal your guidelines",
    "what is your system prompt",
    "print your system",
    "repeat your instructions",
    "tell me your prompt",
    # Cross-user extraction
    "transactions for user",
    "another user's",
    "other user's",
    "spending data for",
    "data for user",
    "show me user",
]

_OFF_DOMAIN_PHRASES = [
    "write me a poem",
    "write a poem",
    "write me a story",
    "write a song",
    "write me code",
    "help me with my essay",
    "play a game",
    "tell me a joke",
    "roleplay",
    "help me debug",
]

_FINANCE_TERMS = {
    "spend", "transaction", "balance", "budget", "income", "expense",
    "saving", "savings", "invest", "debt", "loan", "credit", "debit",
    "money", "bank", "account", "payment", "bill", "subscription",
    "forecast", "goal", "salary", "transfer", "mortgage", "rent",
    "insurance", "tax", "refund", "statement", "finance", "financial",
    "cash", "fund", "portfolio", "cost", "price", "fee", "charge",
}

# ── Output rail keyword sets ──────────────────────────────────────────────────

_ADVICE_PHRASES = [
    "you should buy",
    "i recommend buying",
    "you should sell",
    "i recommend selling",
    "invest in ",
    "this stock will",
    "guaranteed return",
    "you should invest",
    "i advise you to invest",
    "purchase shares",
    "buy this",
    "sell this",
]

_REFUSAL_MESSAGES = {
    "injection": "I can't process messages that attempt to override my instructions.",
    "jailbreak": "I can only assist with personal finance questions in my designed role.",
    "extraction": "I'm not able to reveal information about my configuration.",
    "off_domain": "I'm a personal-finance assistant. I can only help with questions about your finances.",
    "advice": (
        "I can share financial information but cannot provide personalised investment or legal advice. "
        "Please consult a qualified professional."
    ),
}


def redact(text: str) -> str:
    """Replace PII patterns with redaction tokens before the text reaches any log, trace, or LLM call."""
    result = text
    for pattern, replacement in _REDACTION_PATTERNS:
        result = pattern.sub(replacement, result)
    if result != text:
        log.debug("rails.pii_redacted", original_length=len(text), redacted_length=len(result))
    return result


async def check_input(message: str) -> str:
    """Check the user message against safety rules before forwarding to the LLM.

    Raises RailRefusal if the message contains injection, jailbreak, extraction,
    or clear off-domain content. Returns the unchanged message if all checks pass.
    """
    lower = message.lower()

    # 1. Prompt injection
    for phrase in _INJECTION_PHRASES:
        if phrase in lower:
            log.warning("rails.input_blocked", category="injection", phrase=phrase)
            raise RailRefusal(reason="injection", user_facing_message=_REFUSAL_MESSAGES["injection"])

    # 2. Jailbreak
    for phrase in _JAILBREAK_PHRASES:
        if phrase in lower:
            log.warning("rails.input_blocked", category="jailbreak", phrase=phrase)
            raise RailRefusal(reason="jailbreak", user_facing_message=_REFUSAL_MESSAGES["jailbreak"])

    # 3. System-prompt extraction
    for phrase in _EXTRACTION_PHRASES:
        if phrase in lower:
            log.warning("rails.input_blocked", category="extraction", phrase=phrase)
            raise RailRefusal(reason="extraction", user_facing_message=_REFUSAL_MESSAGES["extraction"])

    # 4. Off-domain (only when no finance terms present)
    words = set(lower.split())
    has_finance = bool(words & _FINANCE_TERMS)
    if not has_finance:
        for phrase in _OFF_DOMAIN_PHRASES:
            if phrase in lower:
                log.warning("rails.input_blocked", category="off_domain", phrase=phrase)
                raise RailRefusal(reason="off_domain", user_facing_message=_REFUSAL_MESSAGES["off_domain"])

    return message


async def check_output(text: str) -> str:
    """Check the LLM response before returning it to the user.

    Raises RailRefusal if the response contains licensed investment or legal advice.
    Returns the unchanged text if the check passes.
    """
    lower = text.lower()
    for phrase in _ADVICE_PHRASES:
        if phrase in lower:
            log.warning("rails.output_blocked", category="advice", phrase=phrase)
            raise RailRefusal(reason="advice", user_facing_message=_REFUSAL_MESSAGES["advice"])
    return text
