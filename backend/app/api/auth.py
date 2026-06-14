"""Auth routers: register, JWT login, users/me — wired from fastapi-users (FR-001/002/003)."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import auth_backend, fastapi_users_instance
from app.schemas.user import UserCreate, UserRead, UserUpdate

router = APIRouter()

router.include_router(
    fastapi_users_instance.get_auth_router(auth_backend),
    prefix="/auth/jwt",
    tags=["auth"],
)
router.include_router(
    fastapi_users_instance.get_register_router(UserRead, UserCreate),
    prefix="/auth",
    tags=["auth"],
)
router.include_router(
    fastapi_users_instance.get_users_router(UserRead, UserUpdate),
    prefix="/users",
    tags=["users"],
)
