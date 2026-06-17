"""Unit tests: hybrid RAG retrieval — fusion, no-answer gate, citations, no personal data (FR-013/014)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.infra.embeddings import FakeEmbedder
from app.services.rag.retrieval import _NO_ANSWER_FLOOR, _fuse, retrieve

# ── RRF fusion tests ──────────────────────────────────────────────────────────

def test_rrf_fusion_ranks_both_sources() -> None:
    dense = [
        {"passage_id": "p1", "document_slug": "d1", "heading_path": "h1", "content": "c1", "score": 0.9},
        {"passage_id": "p2", "document_slug": "d1", "heading_path": "h2", "content": "c2", "score": 0.7},
    ]
    sparse = [
        {"passage_id": "p2", "document_slug": "d1", "heading_path": "h2", "content": "c2", "score": 0.8},
        {"passage_id": "p3", "document_slug": "d2", "heading_path": "h3", "content": "c3", "score": 0.6},
    ]
    fused = _fuse(dense, sparse, top_k=3)
    # p2 appears in both dense and sparse — should rank highest
    assert fused[0]["passage_id"] == "p2"
    assert all("fused_score" in p for p in fused)


def test_rrf_fusion_empty_inputs() -> None:
    assert _fuse([], [], top_k=5) == []


def test_rrf_fusion_respects_top_k() -> None:
    dense = [{"passage_id": f"p{i}", "document_slug": "d", "heading_path": "", "content": "", "score": 1.0 - i * 0.1} for i in range(20)]
    fused = _fuse(dense, [], top_k=5)
    assert len(fused) == 5


# ── No-answer gate ────────────────────────────────────────────────────────────

def test_no_answer_floor_value() -> None:
    assert _NO_ANSWER_FLOOR > 0
    assert _NO_ANSWER_FLOOR < 1.0


@pytest.mark.asyncio
async def test_retrieve_no_answer_on_empty_corpus() -> None:
    embedder = FakeEmbedder()
    mock_session = AsyncMock()

    # Both dense and sparse return nothing
    with patch("app.services.rag.retrieval.KnowledgeRepository") as MockRepo:
        repo_instance = MockRepo.return_value
        repo_instance.dense_search = AsyncMock(return_value=[])
        repo_instance.sparse_search = AsyncMock(return_value=[])

        result = await retrieve("What is an emergency fund?", session=mock_session, embedder=embedder)

    assert result == {"no_answer": True}


@pytest.mark.asyncio
async def test_retrieve_returns_citations_on_hit() -> None:
    embedder = FakeEmbedder()
    mock_session = AsyncMock()

    passage = {
        "passage_id": "p1",
        "document_slug": "emergency-funds",
        "heading_path": "How Much Should You Save?",
        "content": "Keep 3-6 months of expenses.",
        "score": 0.95,
    }

    with patch("app.services.rag.retrieval.KnowledgeRepository") as MockRepo:
        repo_instance = MockRepo.return_value
        repo_instance.dense_search = AsyncMock(return_value=[passage])
        repo_instance.sparse_search = AsyncMock(return_value=[passage])

        result = await retrieve("emergency fund size", session=mock_session, embedder=embedder)

    assert "passages" in result
    assert "citations" in result
    assert len(result["citations"]) >= 1
    assert result["citations"][0]["document_slug"] == "emergency-funds"
    assert "no_answer" not in result


def test_citations_contain_no_personal_data() -> None:
    """Citations must only carry slug + heading — never personal figures or identifiers."""
    from app.services.rag.retrieval import _fuse
    dense = [{"passage_id": "p1", "document_slug": "budgeting-basics", "heading_path": "Step 3", "content": "general advice", "score": 0.9}]
    fused = _fuse(dense, [])
    for p in fused:
        assert "user_id" not in p
        assert "amount" not in p
        assert "transaction" not in p.get("content", "").lower()
