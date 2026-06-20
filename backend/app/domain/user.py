"""User domain model: fastapi-users base + is_operator flag (constitution Art. I, DESIGN A)."""

from __future__ import annotations

from datetime import datetime

from fastapi_users_db_sqlalchemy import SQLAlchemyBaseUserTableUUID
from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.base import Base


class User(SQLAlchemyBaseUserTableUUID, Base):  # fastapi-users mixin + our Base; mypy sees no conflict
    __tablename__ = "users"

    is_operator: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Profile fields collected at registration. All nullable so pre-existing rows
    # (e.g. the demo seed) stay valid; `username` is required at the registration
    # schema layer (UserCreate), not the DB, to avoid backfilling existing users.
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    country: Mapped[str | None] = mapped_column(String(64), nullable=True)
    city: Mapped[str | None] = mapped_column(String(64), nullable=True)
    bank_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
