"""Rule-based pre-classifier: deterministic overrides applied before hitting the model-server.

Rules run first; if a row is matched, provenance='rule' and confidence=1.0 — no model call
is made for that row (constitution Art. III — user numbers come from exact logic, not guessing).
Returns (category | None, confidence): None means "send to model".
"""

from __future__ import annotations

import re

# Each rule: (compiled regex, category)
# Applied in order; first match wins.
#
# Two kinds of patterns live here, both HIGH-PRECISION on purpose: a rule match
# bypasses the model AND the review gate (provenance='rule', confidence=1.0, never
# flagged). A false positive is therefore an UN-reviewed wrong label — worse than a
# review flag — so only unambiguous merchant names / keywords belong here. Ambiguous
# short tokens (o2, ee, next, three) are deliberately left to the model.
#
# Why this list is large: the categorizer was trained on a different data
# distribution and returns low confidence on real UK statement strings, so almost
# everything fell through the high operating thresholds into "needs review". Catching
# the common, knowable merchants deterministically here keeps the review queue for
# genuinely uncertain rows (its intended purpose).
_RULES: list[tuple[re.Pattern[str], str]] = [
    # ── Income ────────────────────────────────────────────────────────────────
    (re.compile(r"\bsalary\b|\bpayroll\b|\bwages\b|\bpay\s*credit\b|\bemployer\b", re.I), "income"),
    (re.compile(r"\bhmrc\b|\btax refund\b|\bgov\.?uk\b", re.I), "income"),
    (re.compile(r"\bdividend\b|\bdiv\s+pay\b", re.I), "income"),
    # ── Cash ──────────────────────────────────────────────────────────────────
    (re.compile(r"\batm\b|\bcash withdrawal\b|\bcashpoint\b|\bcash\s+machine\b", re.I), "cash"),
    # ── Mortgage ──────────────────────────────────────────────────────────────
    (re.compile(r"\bmortgage\b|\bhome loan\b", re.I), "mortgage"),
    # ── Savings / Investment ──────────────────────────────────────────────────
    (re.compile(r"\bisaac?\b|\bindividual savings\b|\btransfer to savings\b|\bsavings transfer\b|\bsave the change\b", re.I), "savings"),
    (re.compile(r"\bvanguard\b|\bhargreaves\s+lansdown\b|\bfreetrade\b|\btrading\s*212\b|\bcoinbase\b|\binterest paid\b", re.I), "investment"),
    # ── Groceries ─────────────────────────────────────────────────────────────
    (re.compile(r"\btesco\b|\bsainsbury'?s?\b|\basda\b|\blidl\b|\baldi\b|\bmorrisons\b|\bwaitrose\b|\bco-?op\b|\biceland\b|\bocado\b", re.I), "groceries"),
    # ── Amazon ────────────────────────────────────────────────────────────────
    (re.compile(r"\bamazon\b|\bamzn\b", re.I), "amazon"),
    # ── Dine out ──────────────────────────────────────────────────────────────
    (re.compile(r"\bdeliveroo\b|\bjust\s*eat\b|\buber\s*eats\b|\bnando'?s\b|\bmcdonald'?s?\b|\bkfc\b|\bburger king\b|\bgreggs\b|\bpret\b|\bstarbucks\b|\bcosta\b|\bdomino'?s?\b|\bpizza\b|\brestaurant\b", re.I), "dine_out"),
    # ── Travel (incl. fuel) ───────────────────────────────────────────────────
    (re.compile(r"\btfl\b|\bnational rail\b|\btrainline\b|\beasyjet\b|\bryanair\b|\bbritish airways\b|\buber\s+trip\b|\bgatwick\b|\bheathrow\b", re.I), "travel"),
    (re.compile(r"\bshell\b|\bbp\b|\besso\b|\btexaco\b|\bpetrol\b|\bfuel\b|\bparking\b", re.I), "travel"),
    # ── Entertainment ─────────────────────────────────────────────────────────
    (re.compile(r"\bnetflix\b|\bspotify\b|\bdisney\b|\bapple music\b|\bprime video\b|\byoutube\b|\bcinema\b|\bodeon\b|\bvue\b|\bplaystation\b|\bxbox\b|\bsteam games?\b|\bnintendo\b", re.I), "entertainment"),
    # ── Bills (utilities / telecom / council) ─────────────────────────────────
    (re.compile(r"\bbritish gas\b|\bedf\b|\be\.?on\b|\boctopus energy\b|\bscottish power\b|\bovo energy\b", re.I), "bills"),
    (re.compile(r"\bvodafone\b|\bbt group\b|\bsky\s+digital\b|\bvirgin media\b|\btalktalk\b", re.I), "bills"),
    (re.compile(r"\bcouncil tax\b|\bwater rates\b|\bthames water\b|\banglian water\b|\belectricity\b|\bgas bill\b|\bbroadband\b|\binternet bill\b", re.I), "bills"),
    # ── Insurance ─────────────────────────────────────────────────────────────
    (re.compile(r"\baviva\b|\baxa\b|\bdirect line\b|\badmiral\b|\bchurchill\b|\blegal\s*&?\s*general\b|\binsurance\b", re.I), "insurance"),
    # ── Fitness ───────────────────────────────────────────────────────────────
    (re.compile(r"\bpure\s*gym\b|\bthe gym\b|\bdavid lloyd\b|\bvirgin active\b|\bnuffield health\b|\bpeloton\b|\bgym\b", re.I), "fitness"),
    # ── Clothes ───────────────────────────────────────────────────────────────
    (re.compile(r"\bprimark\b|\bzara\b|\buniqlo\b|\basos\b|\bboohoo\b|\btk\s*maxx\b|\bsports direct\b|\bjd sports\b", re.I), "clothes"),
    # ── Hotels ────────────────────────────────────────────────────────────────
    (re.compile(r"\bpremier inn\b|\btravelodge\b|\bhilton\b|\bmarriott\b|\bholiday inn\b|\bairbnb\b|\bbooking\.com\b", re.I), "hotels"),
    # ── Other shopping ────────────────────────────────────────────────────────
    (re.compile(r"\bwaterstones\b|\bargos\b|\bcurrys\b|\bjohn lewis\b|\bikea\b|\bb&q\b|\bwilko\b|\bsuperdrug\b", re.I), "other_shopping"),
]


def apply_rules(description: str) -> tuple[str | None, float]:
    """Return (category, confidence=1.0) if a rule matches, else (None, 0.0)."""
    for pattern, category in _RULES:
        if pattern.search(description):
            return category, 1.0
    return None, 0.0
