"""Privileged background stats job: computes the global anonymized population prior; user-scoped sessions must never compute cross-user aggregates (constitution Art. II). Stub in Phase 0."""

from __future__ import annotations

# Phase 3+ implements this as a PRIVILEGED job (not under a user RLS context) that
# writes a global anonymized stats table for cold-start forecasting fallback.
