from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from app import config
from app.database import init_db
from app.auth import authenticate, get_current_user

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=config.SECRET_KEY, max_age=28800)
templates = Jinja2Templates(directory="templates")

@app.on_event("startup")
async def startup():
    await init_db()

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "user": None, "error": None})

@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    user = await authenticate(username, password)
    if user is None:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "user": None, "error": "Invalid username or password"},
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
    return templates.TemplateResponse("dashboard.html", {"request": request, "user": user})
