"""Global idempotent retrain trigger: count/cooldown/manual/drift sources; Redis cooldown key; one job per window (constitution Art. III, FR-009, SC-006)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.domain.retrain_run import RetrainRun, TriggerReason
from app.infra.queue import enqueue_retrain
from app.infra.redis import get_redis
from app.repositories.retrain_runs_repo import RetrainRunsRepository

log = structlog.get_logger(__name__)

_COOLDOWN_KEY = "retrain:cooldown"


class RetrainTriggerService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._settings = get_settings()
        self._runs_repo = RetrainRunsRepository(session)

    def _threshold(self) -> int:
        return (
            self._settings.retrain_threshold_demo
            if self._settings.demo_mode
            else self._settings.retrain_threshold_prod
        )

    async def _cooldown_active(self) -> bool:
        redis = get_redis()
        return await redis.exists(_COOLDOWN_KEY) > 0

    async def _set_cooldown(self) -> None:
        redis = get_redis()
        ttl_seconds = int(timedelta(days=self._settings.retrain_cooldown_days).total_seconds())
        await redis.setex(_COOLDOWN_KEY, ttl_seconds, "1")

    async def _reset_cooldown(self) -> None:
        redis = get_redis()
        await redis.delete(_COOLDOWN_KEY)

    async def _build_idempotency_key(self, reason: TriggerReason) -> str:
        now = datetime.now(UTC)
        window = now.strftime("%Y-%U")  # ISO year + week
        return f"retrain:{reason.value}:{window}"

    async def evaluate_and_trigger(
        self,
        *,
        reason: TriggerReason,
        force: bool = False,
        confirmed_count_since_last: int = 0,
    ) -> tuple[RetrainRun | None, bool]:
        """Evaluate whether a retrain should fire.

        Returns (run, enqueued). If cooldown is active and force=False, returns (existing_run, False).
        """
        if not force and await self._cooldown_active():
            latest = await self._runs_repo.get_latest()
            log.info("retrain.trigger.cooldown_active", reason=reason.value)
            return latest, False

        if reason == TriggerReason.correction_count:
            if confirmed_count_since_last < self._threshold():
                log.info(
                    "retrain.trigger.below_threshold",
                    count=confirmed_count_since_last,
                    threshold=self._threshold(),
                )
                return None, False

        idempotency_key = await self._build_idempotency_key(reason)
        run, created = await self._runs_repo.create_or_get(idempotency_key, reason)

        if not created:
            log.info("retrain.trigger.duplicate", idempotency_key=idempotency_key)
            return run, False

        if force:
            await self._reset_cooldown()
        await self._set_cooldown()

        enqueue_retrain(
            run.id,
            idempotency_key=idempotency_key,
            trigger_reason=reason.value,
            demo_mode=self._settings.demo_mode,
        )
        log.info("retrain.trigger.enqueued", run_id=str(run.id), reason=reason.value)
        return run, True

    async def trigger_manual(self, *, force: bool = False) -> tuple[RetrainRun | None, bool]:
        return await self.evaluate_and_trigger(reason=TriggerReason.manual, force=force)

    async def trigger_drift(self) -> tuple[RetrainRun | None, bool]:
        return await self.evaluate_and_trigger(reason=TriggerReason.drift)

    async def trigger_count(self, confirmed_count: int) -> tuple[RetrainRun | None, bool]:
        return await self.evaluate_and_trigger(
            reason=TriggerReason.correction_count,
            confirmed_count_since_last=confirmed_count,
        )
