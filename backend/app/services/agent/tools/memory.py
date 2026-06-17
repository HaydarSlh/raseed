"""write_memory tool: audited durable memory — the ONLY durable-memory path (FR-018/019/020)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.embeddings import get_embedder
from app.repositories.memory_repo import MemoryRepository
from app.services.agent.ratelimit import check_write_rate
from app.services.agent.tools.registry import register_tool


class WriteMemoryInput(BaseModel):
    content: str = Field(..., min_length=1, max_length=1024)
    _session: object | None = None
    _user_id: uuid.UUID | None = None

    model_config = {"arbitrary_types_allowed": True}


async def write_memory(
    content: str,
    _session: AsyncSession | None = None,
    _user_id: uuid.UUID | None = None,
) -> dict:
    """Embed + store memory + emit AuditLog row (FR-018/019). Rate-limited (FR-020)."""
    if _session is None or _user_id is None:
        return {"error": "Session context not available"}

    from app.core.config import get_settings
    from app.domain.audit import AuditLog

    settings = get_settings()
    await check_write_rate(_user_id, limit=settings.write_rate_per_min)

    embedder = get_embedder()
    embedding = await embedder.embed(content)

    repo = MemoryRepository(_session, _user_id)
    mem = await repo.upsert(content, embedding)

    # Audit log — every write_memory call must produce exactly one row (FR-019)
    audit = AuditLog(
        user_id=_user_id,
        action="write_memory",
        detail={"memory_id": str(mem.id), "content_preview": content[:100]},
    )
    _session.add(audit)
    await _session.flush()

    return {"id": str(mem.id), "created_at": str(mem.created_at)}


register_tool("write_memory", WriteMemoryInput, write_memory)
