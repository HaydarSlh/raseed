"""Pydantic schemas for fastapi-users: read, create, update shapes (Art. I layered architecture)."""

from __future__ import annotations

import uuid

from fastapi_users import schemas


class UserRead(schemas.BaseUser[uuid.UUID]):
    is_operator: bool = False
    username: str | None = None
    phone_number: str | None = None
    country: str | None = None
    city: str | None = None
    bank_name: str | None = None


class UserCreate(schemas.BaseUserCreate):
    # Required at registration (also the display name in the UI); the rest optional.
    username: str
    phone_number: str | None = None
    country: str | None = None
    city: str | None = None
    bank_name: str | None = None


class UserUpdate(schemas.BaseUserUpdate):
    is_operator: bool | None = None
    username: str | None = None
    phone_number: str | None = None
    country: str | None = None
    city: str | None = None
    bank_name: str | None = None
