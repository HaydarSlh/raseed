"""Drift detection job: mean-confidence + correction-rate (primary), PSI + new-merchant rate (secondary); fires alerts via the Slack webhook (constitution Art. III). Stub in Phase 0."""

from __future__ import annotations

# Phase 5 implements drift signals and triggers the gated retrain path. The CI
# drift-fire gate runs with the training profile enabled.
