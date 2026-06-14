"""Pydantic schemas for fastapi-users: read, create, update shapes (Art. I layered architecture)."""

from __future__ import annotations

import uuid

from fastapi_users import schemas


class UserRead(schemas.BaseUser[uuid.UUID]):
    is_operator: bool = False


class UserCreate(schemas.BaseUserCreate):
    pass


class UserUpdate(schemas.BaseUserUpdate):
    is_operator: bool | None = None
