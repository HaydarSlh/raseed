"""Offline corpus ingestion: embed rag-corpus/*.md into knowledge_passages (idempotent by hash)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.embeddings import BaseEmbedder
from app.repositories.knowledge_repo import KnowledgeRepository
from app.services.rag.chunking import chunk_markdown

log = structlog.get_logger(__name__)

_CORPUS_DIR = Path(__file__).parent.parent.parent.parent.parent / "rag-corpus"


async def ingest_corpus(
    session: AsyncSession,
    embedder: BaseEmbedder,
    *,
    corpus_dir: Path | None = None,
) -> dict[str, int]:
    """Embed and store all markdown docs in corpus_dir. Idempotent by content hash."""
    corpus_dir = corpus_dir or _CORPUS_DIR
    repo = KnowledgeRepository(session)
    stats = {"documents": 0, "passages": 0, "skipped": 0}

    for md_file in sorted(corpus_dir.glob("*.md")):
        if md_file.name == "SOURCES.md":
            continue

        text = md_file.read_text(encoding="utf-8")
        content_hash = hashlib.sha256(text.encode()).hexdigest()
        slug = md_file.stem
        title = _extract_title(text) or slug

        # Check if already ingested with same hash
        existing = await _get_existing_document(repo, slug, session)
        if existing and existing.content_hash == content_hash:
            log.info("ingest.skip", slug=slug, reason="hash_unchanged")
            stats["skipped"] += 1
            continue

        # Upsert the document record
        doc = await repo.upsert_document(slug=slug, title=title, content_hash=content_hash)
        await repo.delete_passages_for_document(doc.id)

        # Chunk and embed
        passages = chunk_markdown(text)
        for passage in passages:
            p_hash = hashlib.sha256(passage.content.encode()).hexdigest()
            embedding = await embedder.embed(passage.content)
            await repo.insert_passage(
                document_id=doc.id,
                heading_path=passage.heading_path,
                ordinal=passage.ordinal,
                content=passage.content,
                content_hash=p_hash,
                embedding=embedding,
                tsv_text=passage.content,
            )
            stats["passages"] += 1

        stats["documents"] += 1
        log.info("ingest.document", slug=slug, passages=len(passages))

    await session.commit()
    return stats


def _extract_title(text: str) -> str | None:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return None


async def _get_existing_document(repo: KnowledgeRepository, slug: str, session: AsyncSession):
    from sqlalchemy import select

    from app.domain.knowledge import KnowledgeDocument
    result = await session.execute(select(KnowledgeDocument).where(KnowledgeDocument.slug == slug))
    return result.scalar_one_or_none()
