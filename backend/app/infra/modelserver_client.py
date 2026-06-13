"""HTTP client to the lean model-server; awaited calls with timeout + retry (constitution Art. I/V). Stub in Phase 0."""

from __future__ import annotations

# Phase 2+ attaches an httpx.AsyncClient pointed at settings.modelserver_url. In
# Phase 0 the server reports "no model loaded"; this client is wired but unused.
