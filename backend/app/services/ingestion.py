"""Core ingestion function: the single path all entry points (upload, form, agent tool) share.

Pipeline per row:
  ParsedRow → rules → [model-server] → confidence gate → normalize → dedup-insert

After all rows are inserted the recompute job is enqueued so derived data (forecast,
anomalies, subscriptions) is always fresh (constitution Art. V).

Constitution invariants enforced here:
  Art. II  — user_id on every row; RLS is the backstop
  Art. III — provenance tagged on every row; LLM relabels quarantined (needs_review)
  Art. V   — enqueue recompute on every write
"""

from __future__ import annotations

import uuid
from pathlib import Path

import yaml

from app.domain.transaction import Provenance
from app.infra.modelserver_client import ModelServerClient
from app.infra.queue import enqueue_recompute
from app.repositories.transactions_repo import TransactionsRepository
from app.schemas.ingestion import IngestResult, ParsedRow
from app.services.rules import apply_rules

# Load per-category thresholds once at module level from the committed YAML.
_THRESHOLDS_PATH = Path(__file__).parents[4] / "eval_thresholds.yaml"


def _load_thresholds() -> dict[str, float | str]:
    try:
        data = yaml.safe_load(_THRESHOLDS_PATH.read_text())
        return data.get("categorizer", {}).get("operating_thresholds", {})  # type: ignore[return-value]
    except Exception:
        return {}


_THRESHOLDS: dict[str, float | str] = _load_thresholds()


def _normalize(description: str) -> str:
    return description.lower().strip()


def _passes_gate(category: str, confidence: float) -> bool:
    threshold = _THRESHOLDS.get(category, 0.0)
    if threshold == "always_review":
        return False
    return confidence >= float(threshold)  # type: ignore[arg-type]


async def ingest_transactions(
    user_id: uuid.UUID,
    rows: list[ParsedRow],
    repo: TransactionsRepository,
    model_client: ModelServerClient,
) -> IngestResult:
    """Classify, gate, and persist a batch of pre-parsed, pre-scrubbed rows.

    Args:
        user_id:      The authenticated user — applied to every row.
        rows:         ParsedRow list from the parser (already PAN/IBAN-scrubbed).
        repo:         User-scoped TransactionsRepository for the current DB session.
        model_client: Async HTTP client to the lean model-server.

    Returns an IngestResult summary (ingested / needs_review / duplicates_skipped).
    """
    if not rows:
        return IngestResult()

    # ── Step 1: rules pass ────────────────────────────────────────────────────
    rule_results: list[tuple[str | None, float]] = [
        apply_rules(row.description) for row in rows
    ]

    # ── Step 2: model-server call for rows that rules didn't match ────────────
    model_indices = [i for i, (cat, _) in enumerate(rule_results) if cat is None]
    model_results: list[dict] = []
    if model_indices:
        descriptions = [rows[i].description for i in model_indices]
        model_results = await model_client.classify(descriptions)

    model_iter = iter(model_results)

    # ── Step 3: merge + gate ──────────────────────────────────────────────────
    to_insert: list[dict] = []
    needs_review_count = 0

    for i, row in enumerate(rows):
        rule_cat, rule_conf = rule_results[i]

        if rule_cat is not None:
            category = rule_cat
            confidence = rule_conf
            provenance = Provenance.rule
            flagged = False
        else:
            result = next(model_iter)
            category = result.get("label", "other")
            confidence = float(result.get("confidence", 0.0))
            provenance = Provenance.model
            flagged = not _passes_gate(category, confidence)

        if flagged:
            needs_review_count += 1

        normalized = _normalize(row.description)

        to_insert.append(
            {
                "id": uuid.uuid4(),
                "user_id": user_id,
                "provenance": provenance,
                "confidence": confidence,
                "needs_review": flagged,
                "amount": row.amount,
                "currency": row.currency or "GBP",
                "merchant": row.merchant,
                "occurred_at": row.occurred_at,
                "category": category,
                "description": row.description,
                "normalized_description": normalized,
                "is_anomaly": False,
            }
        )

    # ── Step 4: insert with dedup ────────────────────────────────────────────
    inserted = await repo.insert_skip_duplicates(to_insert)
    duplicates_skipped = len(to_insert) - inserted

    # ── Step 5: enqueue recompute (invalidate-on-write) ──────────────────────
    if inserted > 0:
        enqueue_recompute(user_id)

    return IngestResult(
        ingested=inserted,
        needs_review=needs_review_count,
        duplicates_skipped=duplicates_skipped,
    )
