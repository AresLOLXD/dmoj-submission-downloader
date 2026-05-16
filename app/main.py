import re
from datetime import datetime

from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse, HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from app import config
from app.database import init_db
from app.auth import authenticate, get_current_user
from app.admin import router as admin_router
from app.dmoj_client import DMOJClient, ContestNotFoundError
from app.zip_builder import sanitize_name, stream_contest_zip

app = FastAPI()
app.add_middleware(
    SessionMiddleware,
    secret_key=config.SECRET_KEY,
    max_age=28800,
    https_only=True,
    same_site="strict",
)
app.include_router(admin_router)
templates = Jinja2Templates(directory="templates")

@app.on_event("startup")
async def startup():
    await init_db()

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
    request.session.clear()
    return RedirectResponse("/login", status_code=303)

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    user = await get_current_user(request)
    if user is None or not user.is_active:
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse(request, "dashboard.html", {"user": user})


@app.get("/download")
async def download(request: Request, slug: str):
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
        counters: dict[str, dict[str, int]] = {}
        subs = []
        for sub in submissions:
            username = sub["user"]
            problem = sub["problem"]
            sanitized = sanitize_name(username)
            counters.setdefault(sanitized, {}).setdefault(problem, 0)
            counters[sanitized][problem] += 1
            index = counters[sanitized][problem]

            dt = datetime.fromisoformat(sub["date"].replace("Z", "+00:00"))
            source = await dmoj.get_submission_source(sub["id"])
            ext = DMOJClient.language_to_ext(sub.get("language", ""))

            subs.append({
                "sanitized_username": sanitized,
                "problem": problem,
                "index": index,
                "date_str": dt.strftime("%Y-%m-%d"),
                "time_str": dt.strftime("%H-%M-%S"),
                "verdict": sub.get("result", "UNK"),
                "ext": ext,
                "source": source.encode() if isinstance(source, str) else source,
            })

    return StreamingResponse(
        stream_contest_zip(iter(subs)),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{sanitize_name(slug)}.zip"'},
    )
