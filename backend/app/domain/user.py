"""User domain model: fastapi-users base + is_operator flag (constitution Art. I, DESIGN A)."""

from __future__ import annotations

from datetime import datetime

from fastapi_users_db_sqlalchemy import SQLAlchemyBaseUserTableUUID
from sqlalchemy import Boolean, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.base import Base


class User(SQLAlchemyBaseUserTableUUID, Base):  # fastapi-users mixin + our Base; mypy sees no conflict
    __tablename__ = "users"

    is_operator: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
