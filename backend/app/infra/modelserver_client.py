"""HTTP client for the lean model-server: batched classify() with timeout + retry
(constitution Art. I — user numbers come from exact SQL, not RAG; categories are
the only model output that touches user data)."""

from __future__ import annotations

from typing import Any

import httpx

from app.core.config import get_settings

_TIMEOUT = httpx.Timeout(10.0, read=30.0)
_MAX_RETRIES = 2


class ModelServerClient:
    """Thin async wrapper around the model-server /classify endpoint.

    One instance per request; the caller is responsible for providing a fresh
    httpx.AsyncClient (or sharing a lifespan-scoped one).
    """

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._owned = client is None
        self._client = client or httpx.AsyncClient(
            base_url=get_settings().modelserver_url,
            timeout=_TIMEOUT,
        )

    async def __aenter__(self) -> ModelServerClient:
        return self

    async def __aexit__(self, *_: Any) -> None:
        if self._owned:
            await self._client.aclose()

    async def classify(self, descriptions: list[str]) -> list[dict[str, Any]]:
        """Classify a batch of transaction descriptions.

        Returns a list of dicts matching the model-server response schema:
            {"label": str, "confidence": float, "scores": {label: float, ...}}

        Retries up to _MAX_RETRIES times on transient errors (5xx / network).
        Raises httpx.HTTPStatusError on persistent failures so the caller can
        decide whether to quarantine or surface the error.
        """
        if not descriptions:
            return []

        payload = {"inputs": descriptions}
        last_exc: Exception | None = None

        for attempt in range(_MAX_RETRIES + 1):
            try:
                response = await self._client.post("/classify", json=payload)
                response.raise_for_status()
                data = response.json()
                return data["results"]
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                last_exc = exc
                if attempt == _MAX_RETRIES:
                    raise
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code < 500 or attempt == _MAX_RETRIES:
                    raise
                last_exc = exc

        raise RuntimeError("classify() exhausted retries") from last_exc

    async def healthz(self) -> dict[str, Any]:
        response = await self._client.get("/healthz")
        response.raise_for_status()
        return response.json()  # type: ignore[no-any-return]


def get_modelserver_client() -> ModelServerClient:
    """FastAPI dependency: returns a fresh client per request."""
    return ModelServerClient()
