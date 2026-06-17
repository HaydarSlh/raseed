"""CLI wrapper: embed rag-corpus/*.md into knowledge_passages (offline, idempotent by hash).

Usage:
    cd backend
    python -m scripts.ingest_corpus

Set USE_FAKE_LLM=true (or ensure no gemini_api_key) to use FakeEmbedder for local testing.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


async def main() -> None:
    from app.core.config import get_settings
    from app.infra.db import get_session_factory, init_engine
    from app.infra.embeddings import build_embedder
    from app.services.rag.ingest import ingest_corpus

    settings = get_settings()
    init_engine(settings.database_url)
    embedder = build_embedder(
        gemini_api_key=settings.gemini_api_key,
        use_fake=settings.use_fake_llm,
        dim=settings.embedding_dim,
        model=settings.embedding_model,
    )

    factory = get_session_factory()
    async with factory() as session:
        stats = await ingest_corpus(session, embedder)

    print(f"Ingestion complete: {stats}")


if __name__ == "__main__":
    asyncio.run(main())
