"""Auth integration tests: register, login, /users/me with/without token, wrong creds, duplicate email (contracts/auth-api.md, FR-001/002/003, SC-001)."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from main import create_app


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_register_and_login(client: AsyncClient) -> None:
    # register
    r = await client.post("/auth/register", json={"email": "alice@test.com", "password": "correct-horse-battery"})
    assert r.status_code in (200, 201), r.text

    # login
    r = await client.post(
        "/auth/jwt/login",
        data={"username": "alice@test.com", "password": "correct-horse-battery"},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    assert token


@pytest.mark.asyncio
async def test_me_with_token(client: AsyncClient) -> None:
    # register + login
    await client.post("/auth/register", json={"email": "bob@test.com", "password": "hunter2!"})
    r = await client.post(
        "/auth/jwt/login",
        data={"username": "bob@test.com", "password": "hunter2!"},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    token = r.json()["access_token"]

    # /users/me with token → 200
    r = await client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == "bob@test.com"

    # /users/me without token → 401
    r = await client.get("/users/me")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_wrong_password_rejected(client: AsyncClient) -> None:
    await client.post("/auth/register", json={"email": "carol@test.com", "password": "rightpassword"})
    r = await client.post(
        "/auth/jwt/login",
        data={"username": "carol@test.com", "password": "wrongpassword"},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code in (400, 401, 422)
    assert "access_token" not in r.json()


@pytest.mark.asyncio
async def test_duplicate_email_rejected(client: AsyncClient) -> None:
    await client.post("/auth/register", json={"email": "dave@test.com", "password": "pass1234!"})
    r = await client.post("/auth/register", json={"email": "dave@test.com", "password": "pass1234!"})
    assert r.status_code in (400, 409, 422)
