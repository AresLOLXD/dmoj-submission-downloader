import logging
import re
import time
from datetime import datetime

from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse, HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send
from app import config
from app.database import init_db
from app.auth import authenticate, get_current_user
from app.admin import router as admin_router
from app.dmoj_client import DMOJClient, ContestNotFoundError
from app.zip_builder import sanitize_name, stream_contest_zip
from app.logging_config import configure_logging

configure_logging(config.LOG_LEVEL)
logger = logging.getLogger(__name__)


class LoggingMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        start = time.monotonic()
        status_code = 500

        async def send_wrapper(message: dict) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        await self.app(scope, receive, send_wrapper)
        duration = time.monotonic() - start
        logger.info(
            "%s %s status=%d duration=%.2fs",
            scope["method"],
            scope["path"],
            status_code,
            duration,
        )


app = FastAPI()
app.add_middleware(
    SessionMiddleware,
    secret_key=config.SECRET_KEY,
    max_age=28800,
    https_only=config.HTTPS_ONLY,
    same_site="strict",
)
app.add_middleware(LoggingMiddleware)
app.include_router(admin_router)
templates = Jinja2Templates(directory="templates")

@app.on_event("startup")
async def startup():
    await init_db()

@app.get("/")
async def root():
    return RedirectResponse("/dashboard", status_code=302)

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {"user": None, "error": None})

@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    user = await authenticate(username, password)
    if user is None:
        return templates.TemplateResponse(
            request,
            "login.html",
            {"user": None, "error": "Invalid username or password"},
            status_code=200,
        )
    request.session.clear()
    request.session["user_id"] = user.id
    return RedirectResponse("/dashboard", status_code=303)

@app.post("/logout")
async def logout(request: Request):
    user = await get_current_user(request)
    if user:
        logger.info("logout user=%s", user.username)
    request.session.clear()
    return RedirectResponse("/login", status_code=303)

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    user = await get_current_user(request)
    if user is None or not user.is_active:
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse(request, "dashboard.html", {"user": user})


@app.get("/download")
async def download(request: Request, slug: str, token: str | None = None):
    user = await get_current_user(request)
    if user is None or not user.is_active:
        return RedirectResponse("/login", status_code=302)

    if not re.fullmatch(r"[a-zA-Z0-9_\-]{1,64}", slug):
        return templates.TemplateResponse(
            request,
            "dashboard.html",
            {"user": user, "error": "Slug inválido. Solo se permiten letras, números, guiones y guiones bajos."},
        )

    async with DMOJClient(base_url=config.DMOJ_BASE_URL, token=config.DMOJ_API_TOKEN) as dmoj:
        try:
            await dmoj.get_contest_participants(slug)
        except ContestNotFoundError:
            return templates.TemplateResponse(
                request,
                "dashboard.html",
                {"user": user, "error": f"Concurso '{slug}' no encontrado."},
            )

        submissions = await dmoj.get_contest_submissions(slug)
        sources = await dmoj.get_all_sources([sub["id"] for sub in submissions])

        counters: dict[str, dict[str, int]] = {}
        subs = []
        for sub in submissions:
            source = sources.get(sub["id"])
            if source is None:
                continue

            username = sub["user"]
            problem = sub["problem"]
            sanitized = sanitize_name(username)
            counters.setdefault(sanitized, {}).setdefault(problem, 0)
            counters[sanitized][problem] += 1
            index = counters[sanitized][problem]

            dt = datetime.fromisoformat(sub["date"].replace("Z", "+00:00"))
            ext = DMOJClient.language_to_ext(sub.get("language", ""))

            subs.append({
                "sanitized_username": sanitized,
                "problem": problem,
                "index": index,
                "date_str": dt.strftime("%Y-%m-%d"),
                "time_str": dt.strftime("%H-%M-%S"),
                "verdict": sub.get("result", "UNK"),
                "ext": ext,
                "source": source.encode(),
            })

    headers: dict[str, str] = {"Content-Disposition": f'attachment; filename="{sanitize_name(slug)}.zip"'}
    if token is not None and re.fullmatch(r"[a-zA-Z0-9\-]{1,64}", token):
        # HttpOnly omitted intentionally — JS must read this cookie to dismiss the loading modal
        cookie = f"download_ready={token}; Path=/; SameSite=Strict"
        if config.HTTPS_ONLY:
            cookie += "; Secure"
        headers["Set-Cookie"] = cookie
    return StreamingResponse(
        stream_contest_zip(iter(subs)),
        media_type="application/zip",
        headers=headers,
    )
