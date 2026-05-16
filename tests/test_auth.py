import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database import init_db, create_user
from app import database
import aiosqlite
import bcrypt

TEST_DB = "test_auth.db"

@pytest.fixture(autouse=True)
async def setup(monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", TEST_DB)
    await init_db()
    async with aiosqlite.connect(TEST_DB) as db:
        db.row_factory = aiosqlite.Row
        hashed = bcrypt.hashpw(b"secret", bcrypt.gensalt()).decode()
        await create_user(db, "delegate1", hashed)
    yield
    import os
    os.remove(TEST_DB)

@pytest.mark.asyncio
async def test_login_with_valid_credentials_redirects_to_dashboard():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/login", data={"username": "delegate1", "password": "secret"}, follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/dashboard"

@pytest.mark.asyncio
async def test_login_with_invalid_credentials_shows_error():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/login", data={"username": "delegate1", "password": "wrong"})
    assert response.status_code == 200
    assert b"Invalid" in response.content

@pytest.mark.asyncio
async def test_dashboard_redirects_to_login_when_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/dashboard", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["location"]

@pytest.mark.asyncio
async def test_logout_clears_session():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/login", data={"username": "delegate1", "password": "secret"})
        logout_response = await client.post("/logout", follow_redirects=False)
    assert logout_response.status_code == 302
    assert "/login" in logout_response.headers["location"]
