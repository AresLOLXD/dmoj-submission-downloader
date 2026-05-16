#!/usr/bin/env python3
"""Bootstrap the first admin user. Run once after initial deployment."""
import asyncio
import bcrypt
import aiosqlite
import sys
from app.database import DB_PATH, init_db, create_user, get_user_by_username


async def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: python create_admin.py <username> <password>")
        sys.exit(1)

    username, password = sys.argv[1], sys.argv[2]
    await init_db()

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        existing = await get_user_by_username(db, username)
        if existing:
            print(f"Error: user '{username}' already exists.")
            sys.exit(1)
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        user = await create_user(db, username, hashed, is_admin=True)

    print(f"Admin '{user.username}' created successfully.")


if __name__ == "__main__":
    asyncio.run(main())
