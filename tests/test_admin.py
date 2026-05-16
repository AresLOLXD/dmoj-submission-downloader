import pytest
import bcrypt
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database import init_db, create_user, get_user_by_username
from app import database
import aiosqlite

TEST_DB = "test_admin.db"

@pytest.fixture(autouse=True)
async def setup(monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", TEST_DB)
    await init_db()
    async with aiosqlite.connect(TEST_DB) as db:
        db.row_factory = aiosqlite.Row
        hashed_admin = bcrypt.hashpw(b"adminpass", bcrypt.gensalt()).decode()
        hashed_user = bcrypt.hashpw(b"userpass", bcrypt.gensalt()).decode()
        await create_user(db, "admin1", hashed_admin, is_admin=True)
        await create_user(db, "delegate1", hashed_user, is_admin=False)
    yield
    import os
    os.remove(TEST_DB)

@pytest.mark.asyncio
async def test_admin_page_accessible_by_admin():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client:
        await client.post("/login", data={"username": "admin1", "password": "adminpass"})
        response = await client.get("/admin")
    assert response.status_code == 200
    assert b"delegate1" in response.content

@pytest.mark.asyncio
async def test_admin_page_redirects_non_admin():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client:
        await client.post("/login", data={"username": "delegate1", "password": "userpass"})
        response = await client.get("/admin", follow_redirects=False)
    assert response.status_code == 302

@pytest.mark.asyncio
async def test_create_user_via_admin():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client:
        await client.post("/login", data={"username": "admin1", "password": "adminpass"})
        response = await client.post("/admin/users", data={"username": "newuser", "password": "newpass", "is_admin": ""}, follow_redirects=False)
    assert response.status_code == 303
    async with aiosqlite.connect(TEST_DB) as db:
        db.row_factory = aiosqlite.Row
        user = await get_user_by_username(db, "newuser")
    assert user is not None

@pytest.mark.asyncio
async def test_deactivate_user_via_admin():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client:
        await client.post("/login", data={"username": "admin1", "password": "adminpass"})
        resp = await client.get("/admin")
    async with aiosqlite.connect(TEST_DB) as db:
        db.row_factory = aiosqlite.Row
        delegate = await get_user_by_username(db, "delegate1")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client:
        await client.post("/login", data={"username": "admin1", "password": "adminpass"})
        response = await client.post(f"/admin/users/{delegate.id}/toggle", follow_redirects=False)
    assert response.status_code == 303
    async with aiosqlite.connect(TEST_DB) as db:
        db.row_factory = aiosqlite.Row
        updated = await get_user_by_username(db, "delegate1")
    assert updated.is_active is False


@pytest.mark.asyncio
async def test_create_user_logs_info(caplog):
    import logging
    with caplog.at_level(logging.INFO, logger="app.admin"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client:
            await client.post("/login", data={"username": "admin1", "password": "adminpass"})
            await client.post("/admin/users", data={"username": "newuser", "password": "pw"})
    assert any(
        "user_created" in r.message and "admin1" in r.message and "newuser" in r.message
        for r in caplog.records
    )


@pytest.mark.asyncio
async def test_toggle_user_logs_info(caplog):
    import logging
    with caplog.at_level(logging.INFO, logger="app.admin"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client:
            await client.post("/login", data={"username": "admin1", "password": "adminpass"})
            async with aiosqlite.connect(TEST_DB) as db:
                db.row_factory = aiosqlite.Row
                from app.database import get_user_by_username
                target = await get_user_by_username(db, "delegate1")
            await client.post(f"/admin/users/{target.id}/toggle")
    assert any("user_toggled" in r.message and "admin1" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_reset_password_logs_info(caplog):
    import logging
    with caplog.at_level(logging.INFO, logger="app.admin"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client:
            await client.post("/login", data={"username": "admin1", "password": "adminpass"})
            async with aiosqlite.connect(TEST_DB) as db:
                db.row_factory = aiosqlite.Row
                from app.database import get_user_by_username
                target = await get_user_by_username(db, "delegate1")
            await client.post(f"/admin/users/{target.id}/reset-password", data={"new_password": "newpw"})
    assert any("password_reset" in r.message and "admin1" in r.message for r in caplog.records)
