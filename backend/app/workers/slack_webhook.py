"""Slack webhook sender: ops signals ONLY — never user-level transaction data; URL from Vault; timeout/retry/backoff, non-blocking (constitution Art. II/V). Stub in Phase 0."""

from __future__ import annotations

# Phase 5 implements the webhook. Payloads carry ops signals (drift fired, retrain
# promoted) only — no user-level data ever crosses this boundary.
