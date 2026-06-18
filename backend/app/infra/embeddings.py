"""Embedder: sole home of embed(). Hosted Gemini (768-dim) + FakeEmbedder for CI (constitution Art. V)."""

from __future__ import annotations

import abc
import hashlib
import time

import structlog

from app.core.observability import span, with_retry

log = structlog.get_logger(__name__)

# Simple TTL cache entry
_TTL_SECONDS = 300  # 5 minutes


class BaseEmbedder(abc.ABC):
    @abc.abstractmethod
    async def embed(self, text: str) -> list[float]: ...


class FakeEmbedder(BaseEmbedder):
    """Deterministic test double — hash-seeded vector, no API call (Art. V CI gate)."""

    def __init__(self, dim: int = 768) -> None:
        self._dim = dim

    async def embed(self, text: str) -> list[float]:
        import random

        seed = int(hashlib.sha256(text.encode()).hexdigest(), 16) % (2**32)
        rng = random.Random(seed)
        vec = [rng.gauss(0, 1) for _ in range(self._dim)]
        norm = sum(x * x for x in vec) ** 0.5 or 1.0
        return [x / norm for x in vec]


class GeminiEmbedder(BaseEmbedder):
    """Hosted Gemini embedding API (reuses gemini_api_key; no separate key — DECISIONS.md)."""

    def __init__(self, api_key: str, model: str = "models/text-embedding-004", dim: int = 768) -> None:
        self._api_key = api_key
        self._model = model
        self._dim = dim
        # Simple in-process TTL cache: {text_hash -> (embedding, expires_at)}
        self._cache: dict[str, tuple[list[float], float]] = {}

    async def embed(self, text: str) -> list[float]:
        cache_key = hashlib.sha256(text.encode()).hexdigest()
        now = time.monotonic()
        if cache_key in self._cache:
            vec, expires = self._cache[cache_key]
            if now < expires:
                return vec

        vec = await self._call_gemini(text)
        self._cache[cache_key] = (vec, now + _TTL_SECONDS)
        return vec

    async def _call_gemini(self, text: str) -> list[float]:
        import google.genai as genai
        from google.genai import types

        async for attempt in with_retry(max_attempts=3, timeout=15.0):
            with attempt:
                with span("embedder.gemini", model=self._model):
                    client = genai.Client(api_key=self._api_key)
                    response = await client.aio.models.embed_content(
                        model=self._model,
                        contents=text,
                        # gemini-embedding-001 defaults to 3072 dims; request the
                        # configured dimension to match the pgvector column width.
                        config=types.EmbedContentConfig(output_dimensionality=self._dim),
                    )
                    embeddings = response.embeddings or []
                    values: list[float] = list(embeddings[0].values or [])
                    # Gemini only returns unit-normalized vectors at the full 3072
                    # dim; for truncated dims we normalize so cosine/IP scores are
                    # comparable (and consistent with FakeEmbedder).
                    norm = sum(x * x for x in values) ** 0.5
                    if norm > 0:
                        values = [x / norm for x in values]
                    log.debug("embedder.gemini.ok", dim=len(values))
                    return values
        raise RuntimeError("Gemini embedding retries exhausted")  # pragma: no cover


def build_embedder(*, gemini_api_key: str = "", use_fake: bool = False, dim: int = 768, model: str = "models/text-embedding-004") -> BaseEmbedder:
    if use_fake or not gemini_api_key:
        log.info("embedder.using_fake")
        return FakeEmbedder(dim=dim)
    return GeminiEmbedder(api_key=gemini_api_key, model=model, dim=dim)


_embedder: BaseEmbedder | None = None


def init_embedder(embedder: BaseEmbedder) -> None:
    global _embedder
    _embedder = embedder


def get_embedder() -> BaseEmbedder:
    assert _embedder is not None, "Embedder not initialised — call init_embedder() in lifespan"
    return _embedder
