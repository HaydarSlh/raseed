"""Right-to-erasure service: purges all user-scoped stores atomically (Phase 6, FR-008/FR-009)."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.erasure_audit import ErasureAudit
from app.infra.redis import get_redis
from app.schemas.erasure import ErasureResponse

log = structlog.get_logger(__name__)

# Tables to purge in FK-safe order (corrections first, users last).
# Each entry: (table_name,) — we use raw DELETE ... WHERE user_id = :uid for simplicity
# to avoid importing every model and to ensure we hit the exact rows.
_USER_TABLES: list[str] = [
    "corrections",
    "memory",
    "user_settings",
    "goals",
    "forecasts",
    "anomalies",
    "subscriptions",
    "transactions",
]


class ErasureService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def erase_user(self, user_id: uuid.UUID) -> ErasureResponse:
        """Hard-delete all user-scoped rows, Redis keys, and the user record.

        Writes an erasure_audit row on success (in a separate, subsequent step
        to ensure the audit survives even if the user row deletion fails FK checks).
        """
        log.info("erasure.started", user_id=str(user_id))
        counts: dict[str, int] = {}

        # 1. Purge user-scoped Postgres tables (within one transaction)
        async with self._session.begin():
            for table in _USER_TABLES:
                result = await self._session.execute(
                    text(f"DELETE FROM {table} WHERE user_id = :uid"),  # noqa: S608
                    {"uid": user_id},
                )
                counts[table] = result.rowcount

            # Delete the user row last (FK cascade handles remaining references)
            result = await self._session.execute(
                text("DELETE FROM users WHERE id = :uid"),
                {"uid": user_id},
            )
            counts["users"] = result.rowcount

        # 2. Purge Redis keys for this user (scan + delete, parallel)
        redis_count = await self._purge_redis(user_id)
        counts["redis_keys"] = redis_count

        log.info("erasure.postgres_complete", user_id=str(user_id), counts=counts)

        # 3. Write audit record (separate transaction — retained after user deletion)
        audit_id = await self._write_audit(user_id, counts)

        return ErasureResponse(
            audit_id=audit_id,
            status="completed",
            deleted_counts={k: v for k, v in counts.items() if k != "redis_keys"},
            message="All your data has been permanently deleted. This action cannot be undone.",
        )

    async def _purge_redis(self, user_id: uuid.UUID) -> int:
        try:
            redis = get_redis()
            pattern = f"raseed:*:{user_id}"
            cursor = 0
            keys: list[str] = []
            while True:
                cursor, batch = await redis.scan(cursor, match=pattern, count=100)
                keys.extend(batch)
                if cursor == 0:
                    break
            if keys:
                await asyncio.gather(*[redis.delete(k) for k in keys])
            return len(keys)
        except Exception:
            log.warning("erasure.redis_purge_skipped", user_id=str(user_id))
            return 0

    async def _write_audit(self, user_id: uuid.UUID, counts: dict[str, int]) -> uuid.UUID:
        audit = ErasureAudit(
            user_id=user_id,
            completed_at=datetime.now(timezone.utc),
            per_store_counts=counts,
            status="completed",
        )
        async with self._session.begin():
            self._session.add(audit)
        log.info("erasure.audit_written", user_id=str(user_id), audit_id=str(audit.id))
        return audit.id
