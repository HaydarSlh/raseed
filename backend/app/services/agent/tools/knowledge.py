"""search_financial_knowledge tool: hybrid RAG over shared corpus (FR-011/013/014, contracts/tools)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db import get_session_factory
from app.infra.embeddings import get_embedder
from app.services.agent.tools.registry import register_tool
from app.services.rag.retrieval import retrieve


class SearchKnowledgeInput(BaseModel):
    query: str


async def search_financial_knowledge(
    query: str,
    *,
    _session: AsyncSession | None = None,
    _user_id: uuid.UUID | None = None,
) -> dict:
    """Hybrid RAG retrieval; returns passages+citations or no_answer (FR-014).

    The knowledge corpus is shared (no RLS, Art. IV) so this tool creates its own
    session rather than using the RLS-scoped one injected by the agent loop. The
    _session/_user_id kwargs are accepted but unused — they're injected by dispatch
    into every tool and would otherwise cause a TypeError.
    """
    embedder = get_embedder()
    factory = get_session_factory()
    async with factory() as session:
        result = await retrieve(query, session=session, embedder=embedder)
    return result


register_tool("search_financial_knowledge", SearchKnowledgeInput, search_financial_knowledge)
