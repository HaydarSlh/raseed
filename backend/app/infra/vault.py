"""Vault adapter: resolves all secrets at startup; nothing hardcoded (constitution Art. V). Stub in Phase 0."""

from __future__ import annotations

# Phase 1 attaches a Vault client (settings.vault_addr/token) that loads secrets at
# startup. The env-file path is the explicitly documented trim rung, not a silent
# default.
