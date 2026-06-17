"""Knowledge repository: dense (pgvector cosine) and sparse (FTS) queries over the shared corpus."""

from __future__ import annotations

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.knowledge import KnowledgeDocument, KnowledgePassage


class KnowledgeRepository:
    """No user_id filter — the corpus is shared (no RLS on knowledge tables, Art. IV)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def dense_search(self, embedding: list[float], *, limit: int = 10) -> list[dict]:
        """Cosine nearest-neighbour over passage embeddings."""
        if not embedding:
            return []
        vec_str = "[" + ",".join(str(x) for x in embedding) + "]"
        result = await self._session.execute(
            text(
                "SELECT kp.id, kp.document_id, kp.heading_path, kp.content, "
                "1 - (kp.embedding <=> cast(:vec AS vector)) AS score "
                "FROM knowledge_passages kp "
                "WHERE kp.embedding IS NOT NULL "
                "ORDER BY kp.embedding <=> cast(:vec AS vector) "
                "LIMIT :lim"
            ),
            {"vec": vec_str, "lim": limit},
        )
        rows = result.fetchall()
        passages = []
        for row in rows:
            doc_result = await self._session.execute(
                select(KnowledgeDocument).where(KnowledgeDocument.id == row.document_id)
            )
            doc = doc_result.scalar_one_or_none()
            passages.append({
                "passage_id": str(row.id),
                "document_id": str(row.document_id),
                "document_slug": doc.slug if doc else "",
                "heading_path": row.heading_path,
                "content": row.content,
                "score": float(row.score),
            })
        return passages

    async def sparse_search(self, query: str, *, limit: int = 10) -> list[dict]:
        """Postgres full-text search (ts_rank) over passage tsvectors."""
        if not query.strip():
            return []
        result = await self._session.execute(
            text(
                "SELECT kp.id, kp.document_id, kp.heading_path, kp.content, "
                "ts_rank(kp.tsv, plainto_tsquery('english', :q)) AS score "
                "FROM knowledge_passages kp "
                "WHERE kp.tsv @@ plainto_tsquery('english', :q) "
                "ORDER BY score DESC "
                "LIMIT :lim"
            ),
            {"q": query, "lim": limit},
        )
        rows = result.fetchall()
        passages = []
        for row in rows:
            doc_result = await self._session.execute(
                select(KnowledgeDocument).where(KnowledgeDocument.id == row.document_id)
            )
            doc = doc_result.scalar_one_or_none()
            passages.append({
                "passage_id": str(row.id),
                "document_id": str(row.document_id),
                "document_slug": doc.slug if doc else "",
                "heading_path": row.heading_path,
                "content": row.content,
                "score": float(row.score),
            })
        return passages

    async def upsert_document(self, slug: str, title: str, content_hash: str, source: str = "Raseed", license: str = "CC BY 4.0") -> KnowledgeDocument:
        """Insert or update a document by slug."""
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        stmt = (
            pg_insert(KnowledgeDocument)
            .values(slug=slug, title=title, content_hash=content_hash, source=source, license=license)
            .on_conflict_do_update(
                index_elements=["slug"],
                set_={"title": title, "content_hash": content_hash},
            )
            .returning(KnowledgeDocument)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def delete_passages_for_document(self, document_id) -> None:
        from sqlalchemy import delete
        await self._session.execute(
            delete(KnowledgePassage).where(KnowledgePassage.document_id == document_id)
        )

    async def insert_passage(self, document_id, heading_path: str, ordinal: int, content: str, content_hash: str, embedding: list[float] | None, tsv_text: str | None) -> KnowledgePassage:
        passage = KnowledgePassage(
            document_id=document_id,
            heading_path=heading_path,
            ordinal=ordinal,
            content=content,
            content_hash=content_hash,
            embedding=embedding,
        )
        self._session.add(passage)
        await self._session.flush()
        if tsv_text:
            await self._session.execute(
                text("UPDATE knowledge_passages SET tsv = to_tsvector('english', :txt) WHERE id = :id"),
                {"txt": tsv_text, "id": str(passage.id)},
            )
        return passage
