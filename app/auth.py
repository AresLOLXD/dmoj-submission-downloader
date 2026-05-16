import bcrypt
import aiosqlite
from fastapi import Request
from app.database import get_user_by_username, get_user_by_id
from app import database
from app.models import User
from typing import Optional


async def authenticate(username: str, password: str) -> Optional[User]:
    async with aiosqlite.connect(database.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        user = await get_user_by_username(db, username)
    if user is None or not user.is_active:
        return None
    if not bcrypt.checkpw(password.encode(), user.password_hash.encode()):
        return None
    return user


async def get_current_user(request: Request) -> Optional[User]:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    async with aiosqlite.connect(database.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        return await get_user_by_id(db, user_id)
