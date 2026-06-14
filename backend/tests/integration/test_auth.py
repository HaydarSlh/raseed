"""Auth integration tests: register, login, /users/me with/without token, wrong creds, duplicate email (contracts/auth-api.md, FR-001/002/003, SC-001)."""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from main import create_app


def _email(tag: str) -> str:
    """Generate a unique email per test run to avoid duplicate-key failures."""
    return f"{tag}_{uuid.uuid4().hex[:8]}@test.com"


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_register_and_login(client: AsyncClient) -> None:
    email = _email("alice")
    # register
    r = await client.post("/auth/register", json={"email": email, "password": "correct-horse-battery"})
    assert r.status_code in (200, 201), r.text

    # login
    r = await client.post(
        "/auth/jwt/login",
        data={"username": email, "password": "correct-horse-battery"},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    assert token


@pytest.mark.asyncio
async def test_me_with_token(client: AsyncClient) -> None:
    email = _email("bob")
    await client.post("/auth/register", json={"email": email, "password": "hunter2!"})
    r = await client.post(
        "/auth/jwt/login",
        data={"username": email, "password": "hunter2!"},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    token = r.json()["access_token"]

    # /users/me with token → 200
    r = await client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == email

    # /users/me without token → 401
    r = await client.get("/users/me")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_wrong_password_rejected(client: AsyncClient) -> None:
    email = _email("carol")
    await client.post("/auth/register", json={"email": email, "password": "rightpassword"})
    r = await client.post(
        "/auth/jwt/login",
        data={"username": email, "password": "wrongpassword"},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code in (400, 401, 422)
    assert "access_token" not in r.json()


@pytest.mark.asyncio
async def test_duplicate_email_rejected(client: AsyncClient) -> None:
    email = _email("dave")
    await client.post("/auth/register", json={"email": email, "password": "pass1234!"})
    r = await client.post("/auth/register", json={"email": email, "password": "pass1234!"})
    assert r.status_code in (400, 409, 422)
