"""Privileged population-stats job: aggregates anonymized cross-user spend patterns
into the global population_stats table.

BYPASSRLS role (raseed_stats) — this is the ONLY job that aggregates across users.
User-scoped sessions never run cross-user SQL (constitution Art. II).
k-anonymity guard: categories with < 5 distinct users are suppressed.
"""

from __future__ import annotations

import asyncio
import uuid
from decimal import Decimal  # noqa: I001

import sqlalchemy as sa  # noqa: I001

from app.domain.analytics import PopulationStat
from app.infra.db import create_engine_for_role

_K_ANONYMITY_MIN = 5


async def _run_async() -> None:
    engine = create_engine_for_role("raseed_stats")
    async with engine.begin() as conn:
        rows = await conn.execute(
            sa.text("""
                SELECT
                    category,
                    EXTRACT(DOW FROM occurred_at)::smallint AS day_of_week,
                    AVG(amount::float)                      AS mean_amount,
                    STDDEV(amount::float)                   AS stddev_amount,
                    COUNT(DISTINCT user_id)                 AS user_count
                FROM transactions
                WHERE category IS NOT NULL
                  AND occurred_at IS NOT NULL
                  AND amount IS NOT NULL
                GROUP BY 1, 2
                HAVING COUNT(DISTINCT user_id) >= :k
            """),
            {"k": _K_ANONYMITY_MIN},
        )

        await conn.execute(sa.text("DELETE FROM population_stats"))

        for row in rows:
            await conn.execute(
                sa.insert(PopulationStat).values(
                    id=uuid.uuid4(),
                    category=row.category,
                    day_of_week=row.day_of_week,
                    mean_amount=Decimal(str(round(row.mean_amount, 4))),
                    stddev_amount=Decimal(str(round(row.stddev_amount or 0, 4))),
                    user_count=int(row.user_count),
                )
            )

    await engine.dispose()


def run() -> None:
    """RQ entry point for the stats queue (runs under the raseed_stats DB role)."""
    asyncio.run(_run_async())
