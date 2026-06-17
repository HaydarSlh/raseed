"""Hybrid retrieval: RRF fusion of dense+sparse, no-answer gate, citation assembly (FR-013/014, R4/R5)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.embeddings import BaseEmbedder
from app.repositories.knowledge_repo import KnowledgeRepository

# Reciprocal Rank Fusion constant (k=60 is the standard)
_RRF_K = 60
# Minimum fused score to count as a real hit; below this → no-answer
_NO_ANSWER_FLOOR = 0.01
_DEFAULT_TOP_K = 5


def _rrf_score(rank: int) -> float:
    return 1.0 / (_RRF_K + rank + 1)


def _fuse(dense: list[dict], sparse: list[dict], *, top_k: int = _DEFAULT_TOP_K) -> list[dict]:
    """Reciprocal Rank Fusion over dense and sparse result lists."""
    scores: dict[str, float] = {}
    passage_map: dict[str, dict] = {}

    for rank, p in enumerate(dense):
        pid = p["passage_id"]
        scores[pid] = scores.get(pid, 0.0) + _rrf_score(rank)
        passage_map[pid] = p

    for rank, p in enumerate(sparse):
        pid = p["passage_id"]
        scores[pid] = scores.get(pid, 0.0) + _rrf_score(rank)
        passage_map[pid] = p

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
    result = []
    for pid, score in ranked:
        p = passage_map[pid].copy()
        p["fused_score"] = score
        result.append(p)
    return result


async def retrieve(
    query: str,
    *,
    session: AsyncSession,
    embedder: BaseEmbedder,
    top_k: int = _DEFAULT_TOP_K,
) -> dict:
    """Hybrid retrieval: returns passages with citations or {"no_answer": True}."""
    repo = KnowledgeRepository(session)

    # Dense retrieval
    embedding = await embedder.embed(query)
    dense = await repo.dense_search(embedding, limit=top_k * 2)

    # Sparse retrieval
    sparse = await repo.sparse_search(query, limit=top_k * 2)

    # Fuse
    fused = _fuse(dense, sparse, top_k=top_k)

    if not fused or fused[0].get("fused_score", 0.0) < _NO_ANSWER_FLOOR:
        return {"no_answer": True}

    citations = [
        {"document_slug": p["document_slug"], "heading_path": p["heading_path"]}
        for p in fused
    ]
    # Deduplicate citations by (slug, heading)
    seen: set[tuple[str, str]] = set()
    unique_citations = []
    for c in citations:
        key = (c["document_slug"], c["heading_path"])
        if key not in seen:
            seen.add(key)
            unique_citations.append(c)

    return {"passages": fused, "citations": unique_citations}
