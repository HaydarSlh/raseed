"""Memory repository: user-scoped durable memory with vector upsert + nearest-neighbour recall."""

from __future__ import annotations

from sqlalchemy import select, text

from app.domain.memory import Memory
from app.repositories.base import UserScopedRepository


class MemoryRepository(UserScopedRepository[Memory]):
    model = Memory

    async def upsert(self, content: str, embedding: list[float]) -> Memory:
        mem = Memory(user_id=self._user_id, content=content, embedding=embedding)
        self._session.add(mem)
        await self._session.flush()
        return mem

    async def recall_nearest(self, embedding: list[float], *, limit: int = 5) -> list[Memory]:
        """Return the k most semantically similar memories using pgvector cosine distance."""
        vec_str = "[" + ",".join(str(x) for x in embedding) + "]"
        result = await self._session.execute(
            text(
                "SELECT id FROM memory "
                "WHERE user_id = :uid AND embedding IS NOT NULL "
                "ORDER BY embedding <=> cast(:vec AS vector) "
                "LIMIT :lim"
            ),
            {"uid": str(self._user_id), "vec": vec_str, "lim": limit},
        )
        ids = [row[0] for row in result.fetchall()]
        if not ids:
            return []
        result2 = await self._session.execute(
            select(Memory).where(Memory.id.in_(ids))
        )
        return list(result2.scalars().all())
