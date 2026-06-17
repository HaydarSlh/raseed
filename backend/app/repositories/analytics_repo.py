"""Analytics repositories: per-user Forecast/Anomaly/Subscription (wholesale replace on recompute)
and the global PopulationStat reader (raseed_app has SELECT only — constitution Art. II)."""

from __future__ import annotations

from datetime import date

from sqlalchemy import delete, select

from app.domain.analytics import Anomaly, Forecast, PopulationStat, Subscription
from app.repositories.base import UserScopedRepository


class ForecastRepository(UserScopedRepository[Forecast]):
    model = Forecast

    async def replace_all(self, rows: list[Forecast]) -> None:
        """Delete every existing forecast for the user, then bulk-insert the new horizon."""
        await self._session.execute(
            delete(Forecast).where(Forecast.user_id == self._user_id)
        )
        for row in rows:
            if row.user_id != self._user_id:
                raise ValueError("Cannot insert forecast for a different user.")
            self._session.add(row)
        await self._session.flush()

    async def list_from(self, from_date: date) -> list[Forecast]:
        result = await self._session.execute(
            self._base_query().where(Forecast.horizon_date >= from_date).order_by(Forecast.horizon_date)
        )
        return list(result.scalars().all())


class AnomalyRepository(UserScopedRepository[Anomaly]):
    model = Anomaly

    async def replace_all(self, rows: list[Anomaly]) -> None:
        """Delete all anomaly rows for the user, then insert the freshly detected set."""
        await self._session.execute(
            delete(Anomaly).where(Anomaly.user_id == self._user_id)
        )
        for row in rows:
            if row.user_id != self._user_id:
                raise ValueError("Cannot insert anomaly for a different user.")
            self._session.add(row)
        await self._session.flush()


class SubscriptionRepository(UserScopedRepository[Subscription]):
    model = Subscription

    async def replace_all(self, rows: list[Subscription]) -> None:
        """Replace the detected recurring-charge set wholesale (invalidate-on-write)."""
        await self._session.execute(
            delete(Subscription).where(Subscription.user_id == self._user_id)
        )
        for row in rows:
            if row.user_id != self._user_id:
                raise ValueError("Cannot insert subscription for a different user.")
            self._session.add(row)
        await self._session.flush()


class PopulationStatRepository:
    """Read-only access to the global population stats for raseed_app sessions.

    Written only by the privileged raseed_stats job — this repo never writes
    (constitution Art. II).  No user_id filter because the table has none.
    """

    def __init__(self, session) -> None:  # type: ignore[type-arg]
        self._session = session

    async def get_stats(self, category: str) -> list[PopulationStat]:
        result = await self._session.execute(
            select(PopulationStat).where(PopulationStat.category == category)
        )
        return list(result.scalars().all())

    async def get_all(self) -> list[PopulationStat]:
        result = await self._session.execute(select(PopulationStat))
        return list(result.scalars().all())
