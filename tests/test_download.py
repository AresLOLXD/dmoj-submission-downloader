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
        async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client:
            await client.post("/login", data={"username": "user1", "password": "pass"})
            response = await client.get("/download?slug=nope")
    assert response.status_code == 200
    assert b"no encontrado" in response.content.lower() or b"error" in response.content.lower()

@pytest.mark.asyncio
async def test_download_unauthenticated_redirects():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client:
        response = await client.get("/download?slug=ioi2025", follow_redirects=False)
    assert response.status_code == 302

@pytest.mark.asyncio
async def test_download_returns_zip_with_sources():
    with respx.mock:
        respx.get(f"{BASE}/api/v2/contest/ioi2025").mock(return_value=httpx.Response(200, json={
            "data": {"object": {"key": "ioi2025", "rankings": [{"user": "alice"}]}}
        }))
        respx.get(f"{BASE}/api/v2/submissions").mock(return_value=httpx.Response(200, json={
            "data": {
                "objects": [
                    {"id": 1, "user": "alice", "problem": "prob_a", "result": "AC",
                     "language": "PY3", "date": "2025-05-15T14:30:22+00:00"},
                ],
                "has_more": False
            }
        }))
        respx.get(f"{BASE}/src/1/raw").mock(return_value=httpx.Response(200, text="print('hi')"))

        async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client:
            await client.post("/login", data={"username": "user1", "password": "pass"})
            response = await client.get("/download?slug=ioi2025")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert b"PK" in response.content  # ZIP magic bytes

@pytest.mark.asyncio
async def test_download_index_has_no_gaps_when_source_missing():
    import zipfile, io
    with respx.mock:
        respx.get(f"{BASE}/api/v2/contest/ioi2025").mock(return_value=httpx.Response(200, json={
            "data": {"object": {"key": "ioi2025", "rankings": [{"user": "alice"}]}}
        }))
        respx.get(f"{BASE}/api/v2/submissions").mock(return_value=httpx.Response(200, json={
            "data": {
                "objects": [
                    {"id": 1, "user": "alice", "problem": "prob_a", "result": "AC",
                     "language": "PY3", "date": "2025-05-15T14:30:22+00:00"},
                    {"id": 2, "user": "alice", "problem": "prob_a", "result": "WA",
                     "language": "PY3", "date": "2025-05-15T14:35:00+00:00"},
                    {"id": 3, "user": "alice", "problem": "prob_a", "result": "AC",
                     "language": "PY3", "date": "2025-05-15T14:40:00+00:00"},
                ],
                "has_more": False
            }
        }))
        # Sub 2 returns 403 (no source available)
        respx.get(f"{BASE}/src/1/raw").mock(return_value=httpx.Response(200, text="code1"))
        respx.get(f"{BASE}/src/2/raw").mock(return_value=httpx.Response(403))
        respx.get(f"{BASE}/src/3/raw").mock(return_value=httpx.Response(200, text="code3"))

        async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client:
            await client.post("/login", data={"username": "user1", "password": "pass"})
            response = await client.get("/download?slug=ioi2025")

    assert response.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(response.content))
    names = zf.namelist()
    # Should have index 1 and 2 (not 1 and 3)
    assert any("1_alice" in n for n in names)
    assert any("2_alice" in n for n in names)
    assert not any("3_alice" in n for n in names)
