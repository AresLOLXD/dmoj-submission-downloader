import pytest
import respx
import httpx
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database import init_db, create_user
from app import database
import aiosqlite
import bcrypt

TEST_DB = "test_download.db"
BASE = "https://dmoj.test"

@pytest.fixture(autouse=True)
async def setup(monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", TEST_DB)
    monkeypatch.setattr("app.config.DMOJ_BASE_URL", BASE)
    monkeypatch.setattr("app.config.DMOJ_API_TOKEN", "tok")
    await init_db()
    async with aiosqlite.connect(TEST_DB) as db:
        db.row_factory = aiosqlite.Row
        hashed = bcrypt.hashpw(b"pass", bcrypt.gensalt()).decode()
        await create_user(db, "user1", hashed)
    yield
    import os
    os.remove(TEST_DB)

@pytest.mark.asyncio
async def test_download_unknown_slug_shows_error():
    with respx.mock:
        respx.get(f"{BASE}/api/v2/contest/nope").mock(return_value=httpx.Response(404))
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post("/login", data={"username": "user1", "password": "pass"})
            response = await client.get("/download?slug=nope")
    assert response.status_code == 200
    assert b"no encontrado" in response.content.lower() or b"error" in response.content.lower()

@pytest.mark.asyncio
async def test_download_unauthenticated_redirects():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/download?slug=ioi2025", follow_redirects=False)
    assert response.status_code == 302
