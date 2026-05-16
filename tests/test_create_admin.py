import pytest
from unittest.mock import patch
import sys

TEST_DB = "test_create_admin.db"


@pytest.fixture(autouse=True)
async def setup_db(monkeypatch):
    monkeypatch.setattr("app.database.DB_PATH", TEST_DB)
    import app.database
    await app.database.init_db()
    yield
    import os
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


@pytest.mark.asyncio
async def test_create_admin_creates_user(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["create_admin.py", "adminuser"])
    with patch("getpass.getpass", return_value="securepass123"):
        import create_admin
        await create_admin.main()

    import aiosqlite
    from app.database import get_user_by_username
    async with aiosqlite.connect(TEST_DB) as db:
        db.row_factory = aiosqlite.Row
        user = await get_user_by_username(db, "adminuser")
    assert user is not None
    assert user.is_admin is True


@pytest.mark.asyncio
async def test_create_admin_fails_if_user_exists(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["create_admin.py", "adminuser"])
    with patch("getpass.getpass", return_value="securepass123"):
        import create_admin
        await create_admin.main()

    with pytest.raises(SystemExit) as exc_info:
        monkeypatch.setattr(sys, "argv", ["create_admin.py", "adminuser"])
        with patch("getpass.getpass", return_value="otherpass"):
            await create_admin.main()
    assert exc_info.value.code == 1


@pytest.mark.asyncio
async def test_create_admin_exits_with_wrong_arg_count(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["create_admin.py"])
    with pytest.raises(SystemExit) as exc_info:
        import create_admin
        await create_admin.main()
    assert exc_info.value.code == 1
