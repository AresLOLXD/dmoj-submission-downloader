import logging
import bcrypt
import aiosqlite
from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from app.auth import get_current_user
from app import database
from app.database import (
    get_all_users, create_user, set_user_active, update_password, get_user_by_id
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory="templates")

async def _require_admin(request: Request):
    user = await get_current_user(request)
    if user is None or not user.is_active:
        return None, RedirectResponse("/login", status_code=302)
    if not user.is_admin:
        return None, RedirectResponse("/dashboard", status_code=302)
    return user, None

@router.get("", response_class=HTMLResponse)
async def admin_page(request: Request):
    user, redirect = await _require_admin(request)
    if redirect:
        return redirect
    async with aiosqlite.connect(database.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        users = await get_all_users(db)
    return templates.TemplateResponse(request, "admin.html", {"user": user, "users": users, "error": None})

@router.post("/users")
async def create_user_route(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    is_admin: str = Form(default=""),
):
    user, redirect = await _require_admin(request)
    if redirect:
        return redirect
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    async with aiosqlite.connect(database.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await create_user(db, username, hashed, is_admin=bool(is_admin))
    logger.info("user_created admin=%s username=%s", user.username, username)
    return RedirectResponse("/admin", status_code=303)

@router.post("/users/{user_id}/toggle")
async def toggle_user_active(request: Request, user_id: int):
    user, redirect = await _require_admin(request)
    if redirect:
        return redirect
    async with aiosqlite.connect(database.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        target = await get_user_by_id(db, user_id)
        if target:
            new_active = not target.is_active
            await set_user_active(db, user_id, new_active)
            logger.info("user_toggled admin=%s target=%s active=%s", user.username, user_id, new_active)
    return RedirectResponse("/admin", status_code=303)

@router.post("/users/{user_id}/reset-password")
async def reset_password_route(
    request: Request,
    user_id: int,
    new_password: str = Form(...),
):
    user, redirect = await _require_admin(request)
    if redirect:
        return redirect
    hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    async with aiosqlite.connect(database.DB_PATH) as db:
        await update_password(db, user_id, hashed)
    logger.info("password_reset admin=%s target=%s", user.username, user_id)
    return RedirectResponse("/admin", status_code=303)
