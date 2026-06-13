"""Async SQLAlchemy engine/session adapter; sets and resets the per-request RLS session var `app.user_id` on pooled connections (constitution Art. II). Stub in Phase 0."""

from __future__ import annotations

# Phase 1 attaches: create_async_engine(settings.database_url), an async session
# factory, and a dependency that runs `set_config('app.user_id', <jwt-derived id>)`
# on checkout and RESETs it on release. No engine is opened in Phase 0.
