"""Rule-based pre-classifier: deterministic overrides applied before hitting the model-server.

Rules run first; if a row is matched, provenance='rule' and confidence=1.0 — no model call
is made for that row (constitution Art. III — user numbers come from exact logic, not guessing).
Returns (category | None, confidence): None means "send to model".
"""

from __future__ import annotations

import re

# Each rule: (compiled regex, category)
# Applied in order; first match wins.
_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bsalary\b|\bpayroll\b|\bwages\b|\bpay credit\b", re.I), "income"),
    (re.compile(r"\bdividend\b|\bdiv\s+pay\b", re.I), "income"),
    (re.compile(r"\batm\b|\bcash withdrawal\b|\bcashpoint\b", re.I), "cash"),
    (re.compile(r"\bmortgage\b|\bhome loan\b", re.I), "mortgage"),
    (re.compile(r"\bisaac?\b|\bindividual savings\b", re.I), "savings"),
    (re.compile(r"\btransfer to savings\b|\bsavings transfer\b", re.I), "savings"),
    (re.compile(r"\bcouncil tax\b|\bwater rates\b|\belectricity\b|\bgas bill\b|\bbroadband\b|\binternet bill\b", re.I), "bills"),
    (re.compile(r"\bdirect debit\s+(?:insurance|insur)\b", re.I), "insurance"),
]


def apply_rules(description: str) -> tuple[str | None, float]:
    """Return (category, confidence=1.0) if a rule matches, else (None, 0.0)."""
    for pattern, category in _RULES:
        if pattern.search(description):
            return category, 1.0
    return None, 0.0
