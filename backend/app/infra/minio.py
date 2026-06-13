"""MinIO adapter for model artifacts ONLY — never user data or raw statement files (constitution Art. II). Stub in Phase 0."""

from __future__ import annotations

# Phase 2+ attaches a MinIO client scoped to the model-artifacts bucket. Raw user
# files are never written here (or anywhere) — they are parsed in memory and
# discarded.
