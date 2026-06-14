"""UserManager: fastapi-users identity service; password hashing and user lifecycle hooks (constitution Art. I, FR-001)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator

from fastapi import Depends, Request
from fastapi_users import BaseUserManager, UUIDIDMixin
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.domain.user import User
from app.infra.db import get_async_session

log = get_logger(__name__)


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    @property
    def reset_password_token_secret(self) -> str:  # type: ignore[override]
        return get_settings().jwt_secret

    @property
    def verification_token_secret(self) -> str:  # type: ignore[override]
        return get_settings().jwt_secret

    async def on_after_register(self, user: User, request: Request | None = None) -> None:
        log.info("user.registered", user_id=str(user.id))

    async def on_after_login(self, user: User, request: Request | None = None, response: object | None = None) -> None:
        log.info("user.login", user_id=str(user.id))


async def get_user_db(  # noqa: B008
    session: AsyncSession = Depends(get_async_session),  # noqa: B008
) -> AsyncGenerator[SQLAlchemyUserDatabase[User, uuid.UUID], None]:
    yield SQLAlchemyUserDatabase(session, User)


async def get_user_manager(  # noqa: B008
    user_db: SQLAlchemyUserDatabase[User, uuid.UUID] = Depends(get_user_db),  # noqa: B008
) -> AsyncGenerator[UserManager, None]:
    yield UserManager(user_db)
