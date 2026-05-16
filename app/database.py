import aiosqlite
from datetime import datetime
from typing import Optional
from app.models import User

DB_PATH = "dmoj_downloader.db"

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    username     TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    is_admin     BOOLEAN NOT NULL DEFAULT 0,
    is_active    BOOLEAN NOT NULL DEFAULT 1,
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
)
"""


async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(CREATE_TABLE)
        await db.commit()


def _row_to_user(row: aiosqlite.Row) -> User:
    return User(
        id=row["id"],
        username=row["username"],
        password_hash=row["password_hash"],
        is_admin=bool(row["is_admin"]),
        is_active=bool(row["is_active"]),
        created_at=datetime.fromisoformat(row["created_at"]),
    )


async def get_user_by_username(db: aiosqlite.Connection, username: str) -> Optional[User]:
    async with db.execute("SELECT * FROM users WHERE username = ?", (username,)) as cur:
        row = await cur.fetchone()
    return _row_to_user(row) if row else None


async def get_user_by_id(db: aiosqlite.Connection, user_id: int) -> Optional[User]:
    async with db.execute("SELECT * FROM users WHERE id = ?", (user_id,)) as cur:
        row = await cur.fetchone()
    return _row_to_user(row) if row else None


async def get_all_users(db: aiosqlite.Connection) -> list[User]:
    async with db.execute("SELECT * FROM users ORDER BY created_at DESC") as cur:
        rows = await cur.fetchall()
    return [_row_to_user(r) for r in rows]


async def create_user(db: aiosqlite.Connection, username: str, password_hash: str, is_admin: bool = False) -> User:
    async with db.execute(
        "INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, ?)",
        (username, password_hash, int(is_admin)),
    ) as cur:
        user_id = cur.lastrowid
    await db.commit()
    return await get_user_by_id(db, user_id)


async def set_user_active(db: aiosqlite.Connection, user_id: int, active: bool) -> None:
    await db.execute("UPDATE users SET is_active = ? WHERE id = ?", (int(active), user_id))
    await db.commit()


async def update_password(db: aiosqlite.Connection, user_id: int, password_hash: str) -> None:
    await db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id))
    await db.commit()
