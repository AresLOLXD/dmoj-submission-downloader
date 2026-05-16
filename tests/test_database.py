import pytest
import aiosqlite
from app.database import init_db, create_user, get_user_by_username, get_all_users, set_user_active

TEST_DB = "test_dmoj.db"


@pytest.fixture(autouse=True)
async def setup_db(monkeypatch):
    monkeypatch.setattr("app.database.DB_PATH", TEST_DB)
    await init_db()
    yield
    import os
    os.remove(TEST_DB)


@pytest.mark.asyncio
async def test_create_and_fetch_user():
    async with aiosqlite.connect(TEST_DB) as db:
        db.row_factory = aiosqlite.Row
        user = await create_user(db, "alice", "hashed_pw")
    assert user.username == "alice"
    assert user.is_admin is False
    assert user.is_active is True


@pytest.mark.asyncio
async def test_get_user_by_username_returns_none_for_unknown():
    async with aiosqlite.connect(TEST_DB) as db:
        db.row_factory = aiosqlite.Row
        user = await get_user_by_username(db, "nobody")
    assert user is None


@pytest.mark.asyncio
async def test_set_user_active_toggles_flag():
    async with aiosqlite.connect(TEST_DB) as db:
        db.row_factory = aiosqlite.Row
        user = await create_user(db, "bob", "hashed_pw")
        await set_user_active(db, user.id, False)
        fetched = await get_user_by_username(db, "bob")
    assert fetched.is_active is False


@pytest.mark.asyncio
async def test_get_all_users_returns_created_users():
    async with aiosqlite.connect(TEST_DB) as db:
        db.row_factory = aiosqlite.Row
        await create_user(db, "user1", "hash1")
        await create_user(db, "user2", "hash2")
        users = await get_all_users(db)
    assert len(users) == 2
