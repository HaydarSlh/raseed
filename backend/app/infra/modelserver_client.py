"""HTTP client for the lean model-server: calls /predict per description (concurrent)
with timeout + retry (constitution Art. I — categories are the only model output that
touches user data)."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from app.core.config import get_settings

_TIMEOUT = httpx.Timeout(10.0, read=30.0)
_MAX_RETRIES = 2


class ModelServerClient:
    """Thin async wrapper around the model-server /predict endpoint."""

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

    async def _predict_one(self, description: str) -> dict[str, Any]:
        """Call /predict for a single description with retry. Returns {"label", "confidence"}."""
        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                response = await self._client.post("/predict", json={"description": description})
                response.raise_for_status()
                data = response.json()
                # /predict returns {category, confidence, alternatives, low_confidence}
                return {"label": data["category"], "confidence": float(data["confidence"])}
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                last_exc = exc
                if attempt == _MAX_RETRIES:
                    raise
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code < 500 or attempt == _MAX_RETRIES:
                    raise
                last_exc = exc
        raise RuntimeError("_predict_one() exhausted retries") from last_exc

    async def classify(self, descriptions: list[str]) -> list[dict[str, Any]]:
        """Classify a batch of descriptions concurrently via /predict.

        Returns list of {"label": str, "confidence": float} in input order.
        """
        if not descriptions:
            return []
        return list(await asyncio.gather(*[self._predict_one(d) for d in descriptions]))

    async def healthz(self) -> dict[str, Any]:
        response = await self._client.get("/healthz")
        response.raise_for_status()
        return response.json()  # type: ignore[no-any-return]


def get_modelserver_client() -> ModelServerClient:
    """FastAPI dependency: returns a fresh client per request."""
    return ModelServerClient()
