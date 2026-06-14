"""Auth / current-user dependency ONLY. RLS-scoped session lives in app.db.session (M2 split — no persistence concern here). Identity comes solely from the verified JWT (FR-002)."""

from __future__ import annotations

import uuid

from fastapi_users import FastAPIUsers
from fastapi_users.authentication import AuthenticationBackend, BearerTransport, JWTStrategy

from app.core.config import get_settings
from app.domain.user import User
from app.services.user_service import get_user_manager


def _get_jwt_strategy() -> JWTStrategy[User, uuid.UUID]:
    s = get_settings()
    return JWTStrategy(secret=s.jwt_secret, lifetime_seconds=s.jwt_lifetime_seconds)


bearer_transport = BearerTransport(tokenUrl="/auth/jwt/login")

auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=_get_jwt_strategy,
)

fastapi_users_instance: FastAPIUsers[User, uuid.UUID] = FastAPIUsers[User, uuid.UUID](
    get_user_manager,
    [auth_backend],
)

current_active_user = fastapi_users_instance.current_user(active=True)
