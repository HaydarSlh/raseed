"""Analytics ORM models: per-user derived forecasts/anomalies/subscriptions and the
GLOBAL anonymized population_stats prior. Derived tables are invalidated and recomputed
on transaction writes (constitution Art. V); population_stats has NO user_id and is
written only by the privileged stats job (Art. II)."""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import UUID, Boolean, Date, DateTime, Enum, ForeignKey, Numeric, SmallInteger, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.base import Base


class AnomalyType(enum.StrEnum):
    statistical_outlier = "statistical_outlier"
    duplicate_charge = "duplicate_charge"


class Cadence(enum.StrEnum):
    weekly = "weekly"
    biweekly = "biweekly"
    monthly = "monthly"
    quarterly = "quarterly"
    annual = "annual"
    irregular = "irregular"


class Forecast(Base):
    """One row per day across the 30-day horizon; replaced wholesale on recompute."""

    __tablename__ = "forecasts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    horizon_date: Mapped[date] = mapped_column(Date, nullable=False)
    projected_balance: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    lower_bound: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    upper_bound: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    is_cold_start: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Anomaly(Base):
    __tablename__ = "anomalies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    transaction_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False)
    anomaly_type: Mapped[AnomalyType] = mapped_column(Enum(AnomalyType, name="anomaly_type"), nullable=False)
    score: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    reason: Mapped[str] = mapped_column(String(512), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Subscription(Base):
    """Detected recurring charge (a.k.a. recurring series); replaced wholesale on recompute."""

    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    merchant: Mapped[str] = mapped_column(String(512), nullable=False)
    cadence: Mapped[Cadence] = mapped_column(Enum(Cadence, name="cadence_type"), nullable=False)
    typical_amount: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    last_amount: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    next_charge_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    price_increase: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PopulationStat(Base):
    """GLOBAL anonymized prior — NO user_id, no identifying fields. Written only by the
    privileged population_stats job (raseed_stats BYPASSRLS role); user sessions read only.
    Rows emitted only when the contributing-user count meets the k-anonymity guard."""

    __tablename__ = "population_stats"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category: Mapped[str] = mapped_column(String(128), nullable=False)
    day_of_week: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    mean_amount: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    stddev_amount: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    user_count: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
