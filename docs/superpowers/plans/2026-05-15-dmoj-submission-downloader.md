# DMOJ Submission Downloader Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a FastAPI web app that lets authenticated delegates download all contest submissions from a self-hosted DMOJ instance as a streaming ZIP file.

**Architecture:** FastAPI + Uvicorn behind Caddy, server-side Jinja2 templates with Tailwind CSS, SQLite via aiosqlite for user management, and a single DMOJ API token stored in `.env`. ZIPs are generated via streaming so RAM usage stays constant regardless of contest size.

**Tech Stack:** Python 3.11+, FastAPI, Uvicorn, Jinja2, Tailwind CSS (CDN), httpx, aiosqlite, bcrypt, starlette SessionMiddleware (itsdangerous), zipstream-new, pytest, pytest-asyncio, respx

**Spec:** `docs/superpowers/specs/2026-05-15-dmoj-submission-downloader-design.md`

---

## File Map

| File | Responsibility | Agent |
|------|---------------|-------|
| `app/__init__.py` | Package marker | fastapi-developer |
| `app/config.py` | Settings from `.env` | fastapi-developer |
| `app/main.py` | FastAPI app, middleware, route registration | fastapi-developer |
| `app/database.py` | SQLite connection pool, user CRUD queries | fastapi-developer |
| `app/models.py` | Pydantic models (User, UserCreate) | fastapi-developer |
| `app/auth.py` | Session helpers, login/logout routes, dependency guards | fastapi-developer |
| `app/dmoj_client.py` | Async httpx client wrapping DMOJ API v2 | python-pro |
| `app/zip_builder.py` | Filename sanitization, streaming ZIP generator | python-pro |
| `app/admin.py` | Admin routes (list/create/toggle/reset users) | fastapi-developer |
| `templates/base.html` | Base Tailwind layout | fastapi-developer |
| `templates/login.html` | Login form | fastapi-developer |
| `templates/dashboard.html` | Contest slug form | fastapi-developer |
| `templates/admin.html` | User management table | fastapi-developer |
| `tests/test_zip_builder.py` | Unit tests for sanitization and ZIP structure | python-pro |
| `tests/test_dmoj_client.py` | Unit tests for API client (mocked httpx) | python-pro |
| `tests/test_auth.py` | Integration tests for login/logout/guards | fastapi-developer |
| `tests/test_admin.py` | Integration tests for admin routes | fastapi-developer |
| `create_admin.py` | CLI script to bootstrap first admin | python-pro |
| `.env.example` | Template for environment variables | fastapi-developer |
| `requirements.txt` | Pinned dependencies | fastapi-developer |
| `Caddyfile` | Caddy reverse proxy config | deployment-engineer |
| `dmoj-downloader.service` | systemd unit file | deployment-engineer |

---

## Task 1: Project Scaffolding

**Agent:** `voltagent-lang:fastapi-developer`

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `app/__init__.py`
- Create: `app/config.py`
- Create: `app/main.py`

- [ ] **Step 1: Create `requirements.txt`**

```
fastapi==0.115.0
uvicorn[standard]==0.30.6
jinja2==3.1.4
httpx==0.27.2
aiosqlite==0.20.0
bcrypt==4.2.0
itsdangerous==2.2.0
zipstream-new==1.1.8
python-multipart==0.0.9
pytest==8.3.3
pytest-asyncio==0.24.0
respx==0.21.1
```

- [ ] **Step 2: Create `.env.example`**

```
DMOJ_BASE_URL=https://your-dmoj-instance.com
DMOJ_API_TOKEN=your_token_here
SECRET_KEY=change_this_to_a_long_random_string
```

- [ ] **Step 3: Install dependencies**

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Expected: All packages install without errors.

- [ ] **Step 4: Create `app/__init__.py`**

```python
```

(Empty file — package marker.)

- [ ] **Step 5: Create `app/config.py`**

```python
import os
from dotenv import load_dotenv

load_dotenv()

DMOJ_BASE_URL: str = os.environ["DMOJ_BASE_URL"].rstrip("/")
DMOJ_API_TOKEN: str = os.environ["DMOJ_API_TOKEN"]
SECRET_KEY: str = os.environ["SECRET_KEY"]
```

- [ ] **Step 6: Create skeleton `app/main.py`**

```python
from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from app import config

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=config.SECRET_KEY, max_age=28800)

templates = Jinja2Templates(directory="templates")

@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 7: Verify the skeleton runs**

```bash
cp .env.example .env
# Fill in real values, then:
uvicorn app.main:app --reload
curl http://localhost:8000/health
```

Expected: `{"status":"ok"}`

- [ ] **Step 8: Commit**

```bash
git add requirements.txt .env.example app/
git commit -m "feat: project scaffolding, config, and FastAPI skeleton"
```

---

## Task 2: Database Layer

**Agent:** `voltagent-lang:fastapi-developer`

**Files:**
- Create: `app/models.py`
- Create: `app/database.py`
- Create: `tests/__init__.py`
- Create: `tests/test_database.py`

- [ ] **Step 1: Create `app/models.py`**

```python
from pydantic import BaseModel
from dataclasses import dataclass
from datetime import datetime

@dataclass
class User:
    id: int
    username: str
    password_hash: str
    is_admin: bool
    is_active: bool
    created_at: datetime

class UserCreate(BaseModel):
    username: str
    password: str
    is_admin: bool = False
```

- [ ] **Step 2: Create `app/database.py`**

```python
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
```

- [ ] **Step 3: Create `tests/__init__.py`**

```python
```

- [ ] **Step 4: Write failing tests in `tests/test_database.py`**

```python
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
```

- [ ] **Step 5: Run tests to verify they fail (functions not yet connected)**

```bash
pytest tests/test_database.py -v
```

Expected: PASS — `database.py` is already complete, tests should pass.

- [ ] **Step 6: Wire `init_db` into app startup in `app/main.py`**

Add at the bottom of `app/main.py`:

```python
from app.database import init_db

@app.on_event("startup")
async def startup():
    await init_db()
```

- [ ] **Step 7: Run tests**

```bash
pytest tests/test_database.py -v
```

Expected: All 4 tests PASS.

- [ ] **Step 8: Commit**

```bash
git add app/database.py app/models.py app/main.py tests/
git commit -m "feat: database layer with user CRUD and startup init"
```

---

## Task 3: Auth System

**Agent:** `voltagent-lang:fastapi-developer`

**Files:**
- Create: `app/auth.py`
- Create: `templates/base.html`
- Create: `templates/login.html`
- Modify: `app/main.py`
- Create: `tests/test_auth.py`

- [ ] **Step 1: Write failing tests in `tests/test_auth.py`**

```python
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database import init_db, create_user
from app import database
import aiosqlite
import bcrypt

TEST_DB = "test_auth.db"

@pytest.fixture(autouse=True)
async def setup(monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", TEST_DB)
    await init_db()
    async with aiosqlite.connect(TEST_DB) as db:
        db.row_factory = aiosqlite.Row
        hashed = bcrypt.hashpw(b"secret", bcrypt.gensalt()).decode()
        await create_user(db, "delegate1", hashed)
    yield
    import os
    os.remove(TEST_DB)

@pytest.mark.asyncio
async def test_login_with_valid_credentials_redirects_to_dashboard():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/login", data={"username": "delegate1", "password": "secret"}, follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/dashboard"

@pytest.mark.asyncio
async def test_login_with_invalid_credentials_shows_error():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/login", data={"username": "delegate1", "password": "wrong"})
    assert response.status_code == 200
    assert b"Invalid" in response.content

@pytest.mark.asyncio
async def test_dashboard_redirects_to_login_when_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/dashboard", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["location"]

@pytest.mark.asyncio
async def test_logout_clears_session():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/login", data={"username": "delegate1", "password": "secret"})
        logout_response = await client.post("/logout", follow_redirects=False)
    assert logout_response.status_code == 302
    assert "/login" in logout_response.headers["location"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_auth.py -v
```

Expected: FAIL — routes `/login`, `/dashboard`, `/logout` not defined yet.

- [ ] **Step 3: Create `app/auth.py`**

```python
import bcrypt
import aiosqlite
from fastapi import Request
from fastapi.responses import RedirectResponse
from app.database import get_db, get_user_by_username, get_user_by_id
from app.models import User

async def authenticate(username: str, password: str) -> User | None:
    async with aiosqlite.connect(__import__("app.database", fromlist=["DB_PATH"]).DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        user = await get_user_by_username(db, username)
    if user is None or not user.is_active:
        return None
    if not bcrypt.checkpw(password.encode(), user.password_hash.encode()):
        return None
    return user

async def get_current_user(request: Request) -> User | None:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    async with aiosqlite.connect(__import__("app.database", fromlist=["DB_PATH"]).DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        return await get_user_by_id(db, user_id)

def require_login(request: Request):
    async def _inner():
        user = await get_current_user(request)
        if user is None or not user.is_active:
            return RedirectResponse("/login", status_code=302)
        return user
    return _inner

def require_admin(request: Request):
    async def _inner():
        user = await get_current_user(request)
        if user is None or not user.is_active:
            return RedirectResponse("/login", status_code=302)
        if not user.is_admin:
            return RedirectResponse("/dashboard", status_code=302)
        return user
    return _inner
```

- [ ] **Step 4: Create `templates/base.html`**

```html
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}DMOJ Downloader{% endblock %}</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100 min-h-screen">
    <nav class="bg-white shadow px-6 py-3 flex justify-between items-center">
        <span class="font-bold text-gray-800">DMOJ Downloader</span>
        <div class="flex gap-4 items-center">
            {% if user %}
                <span class="text-gray-600 text-sm">{{ user.username }}</span>
                {% if user.is_admin %}
                    <a href="/admin" class="text-blue-600 text-sm hover:underline">Admin</a>
                {% endif %}
                <form method="post" action="/logout">
                    <button class="text-red-600 text-sm hover:underline">Cerrar sesión</button>
                </form>
            {% endif %}
        </div>
    </nav>
    <main class="max-w-2xl mx-auto mt-10 px-4">
        {% block content %}{% endblock %}
    </main>
</body>
</html>
```

- [ ] **Step 5: Create `templates/login.html`**

```html
{% extends "base.html" %}
{% block title %}Iniciar sesión{% endblock %}
{% block content %}
<div class="bg-white rounded-xl shadow p-8">
    <h1 class="text-2xl font-bold text-gray-800 mb-6">Iniciar sesión</h1>
    {% if error %}
        <p class="text-red-600 text-sm mb-4">{{ error }}</p>
    {% endif %}
    <form method="post" action="/login" class="flex flex-col gap-4">
        <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Usuario</label>
            <input name="username" type="text" required
                class="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500">
        </div>
        <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Contraseña</label>
            <input name="password" type="password" required
                class="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500">
        </div>
        <button type="submit"
            class="bg-blue-600 text-white rounded-lg py-2 font-medium hover:bg-blue-700 transition">
            Entrar
        </button>
    </form>
</div>
{% endblock %}
```

- [ ] **Step 6: Add login/logout/dashboard routes to `app/main.py`**

Replace the contents of `app/main.py` with:

```python
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
            {"request": request, "user": None, "error": "Usuario o contraseña incorrectos"},
            status_code=200,
        )
    request.session["user_id"] = user.id
    return RedirectResponse("/dashboard", status_code=302)

@app.post("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=302)

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    user = await get_current_user(request)
    if user is None or not user.is_active:
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse("dashboard.html", {"request": request, "user": user})
```

- [ ] **Step 7: Run auth tests**

```bash
pytest tests/test_auth.py -v
```

Expected: All 4 tests PASS.

- [ ] **Step 8: Commit**

```bash
git add app/auth.py app/main.py templates/
git commit -m "feat: auth system with login/logout and session-based guards"
```

---

## Task 4: DMOJ API Client

**Agent:** `voltagent-lang:python-pro`

**Files:**
- Create: `app/dmoj_client.py`
- Create: `tests/test_dmoj_client.py`

**Note:** DMOJ API v2 returns paginated results with `{"data": {"objects": [...], "has_more": bool}}`. Adjust response parsing if your instance uses a different schema.

- [ ] **Step 1: Write failing tests in `tests/test_dmoj_client.py`**

```python
import pytest
import respx
import httpx
from app.dmoj_client import DMOJClient, ContestNotFoundError

BASE = "https://dmoj.test"
TOKEN = "test_token"

@pytest.fixture
def client():
    return DMOJClient(base_url=BASE, token=TOKEN)

@pytest.mark.asyncio
async def test_get_contest_participants_returns_usernames(client):
    with respx.mock:
        respx.get(f"{BASE}/api/v2/contest/ioi2025").mock(return_value=httpx.Response(200, json={
            "data": {
                "object": {
                    "key": "ioi2025",
                    "rankings": [{"user": "alice"}, {"user": "bob"}]
                }
            }
        }))
        participants = await client.get_contest_participants("ioi2025")
    assert participants == ["alice", "bob"]

@pytest.mark.asyncio
async def test_get_contest_participants_raises_on_404(client):
    with respx.mock:
        respx.get(f"{BASE}/api/v2/contest/nope").mock(return_value=httpx.Response(404))
        with pytest.raises(ContestNotFoundError):
            await client.get_contest_participants("nope")

@pytest.mark.asyncio
async def test_get_submissions_paginates(client):
    with respx.mock:
        respx.get(f"{BASE}/api/v2/submissions").mock(side_effect=[
            httpx.Response(200, json={
                "data": {
                    "objects": [
                        {"id": 1, "user": "alice", "problem": "prob_a", "result": "AC",
                         "language": "PY3", "date": "2025-05-15T14:30:22"}
                    ],
                    "has_more": True,
                    "next_page_id": 2
                }
            }),
            httpx.Response(200, json={
                "data": {
                    "objects": [
                        {"id": 2, "user": "bob", "problem": "prob_b", "result": "WA",
                         "language": "CPP17", "date": "2025-05-15T15:00:00"}
                    ],
                    "has_more": False
                }
            }),
        ])
        submissions = await client.get_contest_submissions("ioi2025")
    assert len(submissions) == 2
    assert submissions[0]["id"] == 1
    assert submissions[1]["id"] == 2

@pytest.mark.asyncio
async def test_get_submission_source_returns_code(client):
    with respx.mock:
        respx.get(f"{BASE}/api/v2/submission/42").mock(return_value=httpx.Response(200, json={
            "data": {"object": {"id": 42, "source": "print('hello')"}}
        }))
        source = await client.get_submission_source(42)
    assert source == "print('hello')"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_dmoj_client.py -v
```

Expected: FAIL — `DMOJClient` not defined.

- [ ] **Step 3: Create `app/dmoj_client.py`**

```python
import httpx
from typing import Any

LANGUAGE_EXTENSIONS: dict[str, str] = {
    "PY3": "py", "PY2": "py", "CPP17": "cpp", "CPP14": "cpp", "CPP11": "cpp",
    "CPP20": "cpp", "C": "c", "JAVA8": "java", "JAVA11": "java", "JAVA17": "java",
    "KOTLIN": "kt", "RUBY": "rb", "RUST": "rs", "GO": "go", "HS": "hs",
    "JS": "js", "CS": "cs", "PAS": "pas", "D": "d", "SWIFT": "swift",
}

class ContestNotFoundError(Exception):
    pass

class DMOJClient:
    def __init__(self, base_url: str, token: str) -> None:
        self._base = base_url
        self._headers = {"Authorization": f"Bearer {token}"}

    async def get_contest_participants(self, slug: str) -> list[str]:
        async with httpx.AsyncClient(headers=self._headers, timeout=30) as client:
            resp = await client.get(f"{self._base}/api/v2/contest/{slug}")
        if resp.status_code == 404:
            raise ContestNotFoundError(slug)
        resp.raise_for_status()
        rankings = resp.json()["data"]["object"]["rankings"]
        return [r["user"] for r in rankings]

    async def get_contest_submissions(self, slug: str) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        params: dict[str, Any] = {"contest": slug, "page_size": 100}
        async with httpx.AsyncClient(headers=self._headers, timeout=30) as client:
            while True:
                resp = await client.get(f"{self._base}/api/v2/submissions", params=params)
                resp.raise_for_status()
                data = resp.json()["data"]
                results.extend(data["objects"])
                if not data.get("has_more"):
                    break
                params["after"] = data["next_page_id"]
        return results

    async def get_submission_source(self, submission_id: int) -> str:
        async with httpx.AsyncClient(headers=self._headers, timeout=30) as client:
            resp = await client.get(f"{self._base}/api/v2/submission/{submission_id}")
        resp.raise_for_status()
        return resp.json()["data"]["object"]["source"]

    @staticmethod
    def language_to_ext(language: str) -> str:
        return LANGUAGE_EXTENSIONS.get(language, "txt")
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_dmoj_client.py -v
```

Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/dmoj_client.py tests/test_dmoj_client.py
git commit -m "feat: DMOJ API client with pagination and language extension mapping"
```

---

## Task 5: ZIP Streaming Builder

**Agent:** `voltagent-lang:python-pro`

**Files:**
- Create: `app/zip_builder.py`
- Create: `tests/test_zip_builder.py`

- [ ] **Step 1: Write failing tests in `tests/test_zip_builder.py`**

```python
import io
import zipfile
import pytest
from app.zip_builder import sanitize_name, build_submission_filename, stream_contest_zip

def test_sanitize_name_replaces_special_chars():
    assert sanitize_name("user@123") == "user_123"
    assert sanitize_name("José García") == "Jos__Garc_a"
    assert sanitize_name("normal_user-1") == "normal_user-1"

def test_sanitize_name_truncates_to_64_chars():
    long = "a" * 100
    result = sanitize_name(long)
    assert len(result) == 64

def test_sanitize_name_does_not_truncate_short_names():
    assert sanitize_name("alice") == "alice"

def test_build_submission_filename():
    name = build_submission_filename(
        index=1,
        username="user1",
        date_str="2025-05-15",
        time_str="14-30-22",
        verdict="AC",
        ext="py",
    )
    assert name == "1_user1_2025-05-15_14-30-22_AC.py"

def test_stream_contest_zip_produces_valid_zip():
    submissions = [
        {
            "sanitized_username": "user1",
            "problem": "prob_a",
            "index": 1,
            "date_str": "2025-05-15",
            "time_str": "14-30-22",
            "verdict": "AC",
            "ext": "py",
            "source": b"print('hello')",
        }
    ]
    chunks = list(stream_contest_zip(iter(submissions)))
    buffer = io.BytesIO(b"".join(chunks))
    with zipfile.ZipFile(buffer) as zf:
        names = zf.namelist()
        assert "user1/prob_a/1_user1_2025-05-15_14-30-22_AC.py" in names
        assert zf.read("user1/prob_a/1_user1_2025-05-15_14-30-22_AC.py") == b"print('hello')"

def test_stream_contest_zip_multiple_users_and_problems():
    submissions = [
        {"sanitized_username": "alice", "problem": "a", "index": 1, "date_str": "2025-01-01",
         "time_str": "10-00-00", "verdict": "AC", "ext": "py", "source": b"code_a"},
        {"sanitized_username": "bob", "problem": "b", "index": 1, "date_str": "2025-01-01",
         "time_str": "10-05-00", "verdict": "WA", "ext": "cpp", "source": b"code_b"},
    ]
    chunks = list(stream_contest_zip(iter(submissions)))
    buffer = io.BytesIO(b"".join(chunks))
    with zipfile.ZipFile(buffer) as zf:
        names = zf.namelist()
    assert "alice/a/1_alice_2025-01-01_10-00-00_AC.py" in names
    assert "bob/b/1_bob_2025-01-01_10-05-00_WA.cpp" in names
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_zip_builder.py -v
```

Expected: FAIL — `zip_builder` not defined.

- [ ] **Step 3: Create `app/zip_builder.py`**

```python
import re
import zipstream
from typing import Iterator, Any

def sanitize_name(name: str) -> str:
    sanitized = re.sub(r"[^a-zA-Z0-9_\-]", "_", name)
    return sanitized[:64]

def build_submission_filename(index: int, username: str, date_str: str, time_str: str, verdict: str, ext: str) -> str:
    return f"{index}_{username}_{date_str}_{time_str}_{verdict}.{ext}"

def stream_contest_zip(submissions: Iterator[dict[str, Any]]):
    zf = zipstream.ZipFile(mode="w", compression=zipstream.ZIP_DEFLATED)
    for sub in submissions:
        filename = build_submission_filename(
            index=sub["index"],
            username=sub["sanitized_username"],
            date_str=sub["date_str"],
            time_str=sub["time_str"],
            verdict=sub["verdict"],
            ext=sub["ext"],
        )
        arcname = f"{sub['sanitized_username']}/{sub['problem']}/{filename}"
        source = sub["source"]
        zf.writestr(arcname, source if isinstance(source, bytes) else source.encode())
    yield from zf
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_zip_builder.py -v
```

Expected: All 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/zip_builder.py tests/test_zip_builder.py
git commit -m "feat: streaming ZIP builder with filename sanitization"
```

---

## Task 6: Dashboard & Download Route

**Agent:** `voltagent-lang:fastapi-developer`

**Files:**
- Create: `templates/dashboard.html`
- Modify: `app/main.py`
- Create: `tests/test_download.py`

- [ ] **Step 1: Create `templates/dashboard.html`**

```html
{% extends "base.html" %}
{% block title %}Descargar envíos{% endblock %}
{% block content %}
<div class="bg-white rounded-xl shadow p-8">
    <h1 class="text-2xl font-bold text-gray-800 mb-2">Descargar envíos de concurso</h1>
    <p class="text-gray-500 text-sm mb-6">Ingresa el slug del concurso (ej. <code class="bg-gray-100 px-1 rounded">ioi2025</code>)</p>
    {% if error %}
        <div class="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 mb-4 text-sm">{{ error }}</div>
    {% endif %}
    <form method="get" action="/download" class="flex gap-3">
        <input name="slug" type="text" placeholder="slug-del-concurso" required
            class="flex-1 border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500">
        <button type="submit"
            class="bg-blue-600 text-white rounded-lg px-5 py-2 font-medium hover:bg-blue-700 transition whitespace-nowrap">
            Descargar ZIP
        </button>
    </form>
</div>
{% endblock %}
```

- [ ] **Step 2: Write failing tests in `tests/test_download.py`**

```python
import pytest
import respx
import httpx
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database import init_db, create_user
from app import database
import aiosqlite
import bcrypt

TEST_DB = "test_download.db"
BASE = "https://dmoj.test"

@pytest.fixture(autouse=True)
async def setup(monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", TEST_DB)
    monkeypatch.setattr("app.config.DMOJ_BASE_URL", BASE)
    monkeypatch.setattr("app.config.DMOJ_API_TOKEN", "tok")
    await init_db()
    async with aiosqlite.connect(TEST_DB) as db:
        db.row_factory = aiosqlite.Row
        hashed = bcrypt.hashpw(b"pass", bcrypt.gensalt()).decode()
        await create_user(db, "user1", hashed)
    yield
    import os
    os.remove(TEST_DB)

@pytest.mark.asyncio
async def test_download_unknown_slug_shows_error():
    with respx.mock:
        respx.get(f"{BASE}/api/v2/contest/nope").mock(return_value=httpx.Response(404))
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post("/login", data={"username": "user1", "password": "pass"})
            response = await client.get("/download?slug=nope")
    assert response.status_code == 200
    assert b"no encontrado" in response.content.lower() or b"error" in response.content.lower()

@pytest.mark.asyncio
async def test_download_unauthenticated_redirects():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/download?slug=ioi2025", follow_redirects=False)
    assert response.status_code == 302
```

- [ ] **Step 3: Add download route to `app/main.py`**

Add these imports at the top of `app/main.py`:

```python
from fastapi.responses import StreamingResponse
from app import config
from app.dmoj_client import DMOJClient, ContestNotFoundError
from app.zip_builder import sanitize_name, stream_contest_zip
from datetime import datetime
```

Add this route function to `app/main.py`:

```python
@app.get("/download")
async def download(request: Request, slug: str):
    user = await get_current_user(request)
    if user is None or not user.is_active:
        return RedirectResponse("/login", status_code=302)

    dmoj = DMOJClient(base_url=config.DMOJ_BASE_URL, token=config.DMOJ_API_TOKEN)

    try:
        await dmoj.get_contest_participants(slug)
    except ContestNotFoundError:
        return templates.TemplateResponse(
            "dashboard.html",
            {"request": request, "user": user, "error": f"Concurso '{slug}' no encontrado."},
        )

    async def submission_iter():
        submissions = await dmoj.get_contest_submissions(slug)
        counters: dict[str, dict[str, int]] = {}
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

            yield {
                "sanitized_username": sanitized,
                "problem": sanitize_name(problem),
                "index": index,
                "date_str": dt.strftime("%Y-%m-%d"),
                "time_str": dt.strftime("%H-%M-%S"),
                "verdict": sub.get("result", "UNK"),
                "ext": ext,
                "source": source,
            }

    return StreamingResponse(
        stream_contest_zip(submission_iter().__aiter__()),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{slug}.zip"'},
    )
```

**Note:** `stream_contest_zip` receives a sync iterator. Since `submission_iter` is async, update `zip_builder.py` to handle both sync and async iterators, or collect the async iterator into a list before passing:

Replace the `stream_contest_zip` call above with:

```python
    async def collect():
        return [s async for s in submission_iter()]

    subs = await collect()
    return StreamingResponse(
        stream_contest_zip(iter(subs)),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{slug}.zip"'},
    )
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_download.py -v
```

Expected: All 2 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/main.py templates/dashboard.html tests/test_download.py
git commit -m "feat: dashboard and ZIP download route with streaming response"
```

---

## Task 7: Admin Panel

**Agent:** `voltagent-lang:fastapi-developer`

**Files:**
- Create: `app/admin.py`
- Create: `templates/admin.html`
- Modify: `app/main.py`
- Create: `tests/test_admin.py`

- [ ] **Step 1: Write failing tests in `tests/test_admin.py`**

```python
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
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/login", data={"username": "admin1", "password": "adminpass"})
        response = await client.get("/admin")
    assert response.status_code == 200
    assert b"delegate1" in response.content

@pytest.mark.asyncio
async def test_admin_page_redirects_non_admin():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/login", data={"username": "delegate1", "password": "userpass"})
        response = await client.get("/admin", follow_redirects=False)
    assert response.status_code == 302

@pytest.mark.asyncio
async def test_create_user_via_admin():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/login", data={"username": "admin1", "password": "adminpass"})
        response = await client.post("/admin/users", data={"username": "newuser", "password": "newpass", "is_admin": ""}, follow_redirects=False)
    assert response.status_code == 302
    async with aiosqlite.connect(TEST_DB) as db:
        db.row_factory = aiosqlite.Row
        user = await get_user_by_username(db, "newuser")
    assert user is not None

@pytest.mark.asyncio
async def test_deactivate_user_via_admin():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/login", data={"username": "admin1", "password": "adminpass"})
        # get delegate1's id first
        resp = await client.get("/admin")
    # deactivate by posting to /admin/users/{id}/deactivate
    async with aiosqlite.connect(TEST_DB) as db:
        db.row_factory = aiosqlite.Row
        delegate = await get_user_by_username(db, "delegate1")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/login", data={"username": "admin1", "password": "adminpass"})
        response = await client.post(f"/admin/users/{delegate.id}/toggle", follow_redirects=False)
    assert response.status_code == 302
    async with aiosqlite.connect(TEST_DB) as db:
        db.row_factory = aiosqlite.Row
        updated = await get_user_by_username(db, "delegate1")
    assert updated.is_active is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_admin.py -v
```

Expected: FAIL — `/admin` routes not defined.

- [ ] **Step 3: Create `app/admin.py`**

```python
import bcrypt
import aiosqlite
from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from app.auth import get_current_user
from app.database import (
    get_all_users, create_user, set_user_active, update_password, DB_PATH
)

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
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        users = await get_all_users(db)
    return templates.TemplateResponse("admin.html", {"request": request, "user": user, "users": users, "error": None})

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
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await create_user(db, username, hashed, is_admin=bool(is_admin))
    return RedirectResponse("/admin", status_code=302)

@router.post("/users/{user_id}/toggle")
async def toggle_user_active(request: Request, user_id: int):
    user, redirect = await _require_admin(request)
    if redirect:
        return redirect
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        from app.database import get_user_by_id
        target = await get_user_by_id(db, user_id)
        if target:
            await set_user_active(db, user_id, not target.is_active)
    return RedirectResponse("/admin", status_code=302)

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
    async with aiosqlite.connect(DB_PATH) as db:
        await update_password(db, user_id, hashed)
    return RedirectResponse("/admin", status_code=302)
```

- [ ] **Step 4: Register admin router in `app/main.py`**

Add at the top of `app/main.py`:

```python
from app.admin import router as admin_router
```

Add after middleware setup:

```python
app.include_router(admin_router)
```

- [ ] **Step 5: Create `templates/admin.html`**

```html
{% extends "base.html" %}
{% block title %}Panel de administración{% endblock %}
{% block content %}
<div class="bg-white rounded-xl shadow p-8 mb-6">
    <h1 class="text-2xl font-bold text-gray-800 mb-6">Gestión de usuarios</h1>

    {% if error %}
        <div class="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 mb-4 text-sm">{{ error }}</div>
    {% endif %}

    <h2 class="text-lg font-semibold text-gray-700 mb-3">Crear usuario</h2>
    <form method="post" action="/admin/users" class="flex flex-wrap gap-3 mb-8">
        <input name="username" type="text" placeholder="Nombre de usuario" required
            class="border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500">
        <input name="password" type="password" placeholder="Contraseña" required
            class="border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500">
        <label class="flex items-center gap-2 text-sm text-gray-700">
            <input name="is_admin" type="checkbox" value="1" class="rounded"> Administrador
        </label>
        <button type="submit" class="bg-blue-600 text-white rounded-lg px-4 py-2 font-medium hover:bg-blue-700 transition">
            Crear
        </button>
    </form>

    <h2 class="text-lg font-semibold text-gray-700 mb-3">Usuarios</h2>
    <table class="w-full text-sm">
        <thead>
            <tr class="text-left text-gray-500 border-b">
                <th class="pb-2">Usuario</th>
                <th class="pb-2">Rol</th>
                <th class="pb-2">Estado</th>
                <th class="pb-2">Creado</th>
                <th class="pb-2">Acciones</th>
            </tr>
        </thead>
        <tbody>
        {% for u in users %}
            <tr class="border-b last:border-0">
                <td class="py-3 font-medium text-gray-800">{{ u.username }}</td>
                <td class="py-3 text-gray-500">{{ "Admin" if u.is_admin else "Delegado" }}</td>
                <td class="py-3">
                    <span class="px-2 py-1 rounded text-xs font-medium {{ 'bg-green-100 text-green-700' if u.is_active else 'bg-red-100 text-red-700' }}">
                        {{ "Activo" if u.is_active else "Inactivo" }}
                    </span>
                </td>
                <td class="py-3 text-gray-400">{{ u.created_at.strftime("%Y-%m-%d") }}</td>
                <td class="py-3 flex gap-3">
                    <form method="post" action="/admin/users/{{ u.id }}/toggle">
                        <button class="text-yellow-600 hover:underline text-xs">
                            {{ "Desactivar" if u.is_active else "Activar" }}
                        </button>
                    </form>
                    <form method="post" action="/admin/users/{{ u.id }}/reset-password" class="flex gap-1">
                        <input name="new_password" type="password" placeholder="Nueva contraseña"
                            class="border border-gray-300 rounded px-2 py-1 text-xs w-32 focus:outline-none">
                        <button class="text-blue-600 hover:underline text-xs">Resetear</button>
                    </form>
                </td>
            </tr>
        {% endfor %}
        </tbody>
    </table>
</div>
{% endblock %}
```

- [ ] **Step 6: Run tests**

```bash
pytest tests/test_admin.py -v
```

Expected: All 4 tests PASS.

- [ ] **Step 7: Run all tests**

```bash
pytest tests/ -v
```

Expected: All tests PASS.

- [ ] **Step 8: Commit**

```bash
git add app/admin.py app/main.py templates/admin.html tests/test_admin.py
git commit -m "feat: admin panel for user management (create/toggle/reset-password)"
```

---

## Task 8: CLI Admin Bootstrap Script

**Agent:** `voltagent-lang:python-pro`

**Files:**
- Create: `create_admin.py`

- [ ] **Step 1: Create `create_admin.py`**

```python
#!/usr/bin/env python3
"""Bootstrap the first admin user. Run once after initial deployment."""
import asyncio
import bcrypt
import aiosqlite
import sys
from app.database import DB_PATH, init_db, create_user, get_user_by_username

async def main():
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
```

- [ ] **Step 2: Test manually**

```bash
python create_admin.py miadmin mipassword
```

Expected: `Admin 'miadmin' created successfully.`

```bash
python create_admin.py miadmin mipassword
```

Expected: `Error: user 'miadmin' already exists.`

- [ ] **Step 3: Commit**

```bash
git add create_admin.py
git commit -m "feat: CLI script to bootstrap the first admin user"
```

---

## Task 9: Deployment Configuration

**Agent:** `voltagent-infra:deployment-engineer`

**Files:**
- Create: `Caddyfile`
- Create: `dmoj-downloader.service`
- Create: `.env.example` (already done in Task 1 — verify it matches final requirements)

- [ ] **Step 1: Create `Caddyfile`**

```caddyfile
your-domain.com {
    reverse_proxy localhost:8000
}
```

Replace `your-domain.com` with the actual domain before deploying.

- [ ] **Step 2: Create `dmoj-downloader.service`**

```ini
[Unit]
Description=DMOJ Submission Downloader
After=network.target

[Service]
Type=simple
User=dmoj-dl
WorkingDirectory=/opt/dmoj-downloader
EnvironmentFile=/opt/dmoj-downloader/.env
ExecStart=/opt/dmoj-downloader/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 3: Enable and start the service**

```bash
sudo cp dmoj-downloader.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable dmoj-downloader
sudo systemctl start dmoj-downloader
sudo systemctl status dmoj-downloader
```

Expected: `Active: active (running)`

- [ ] **Step 4: Start Caddy**

```bash
sudo caddy start --config Caddyfile
```

Expected: Caddy starts and automatically provisions TLS certificate.

- [ ] **Step 5: Verify end-to-end**

```bash
curl https://your-domain.com/health
```

Expected: `{"status":"ok"}`

- [ ] **Step 6: Commit**

```bash
git add Caddyfile dmoj-downloader.service
git commit -m "feat: Caddy and systemd deployment configuration"
```

---

## Task 10: Security Review

**Agent:** `voltagent-qa-sec:security-auditor`

**Scope:** Review `app/auth.py`, `app/admin.py`, `app/main.py`, and `app/dmoj_client.py` for:
- Session fixation vulnerabilities
- Password hashing correctness (bcrypt cost factor)
- API token exposure (never logged, never returned to client)
- Admin route authorization bypass possibilities
- Cookie security flags (Secure, HttpOnly, SameSite)
- Input sanitization in ZIP filenames

- [ ] **Step 1: Run security review**

Dispatch `voltagent-qa-sec:security-auditor` with the files above and the design spec. Request a written findings report.

- [ ] **Step 2: Address all Critical and High findings**

Fix any issues found before considering the implementation complete.

- [ ] **Step 3: Run full test suite after fixes**

```bash
pytest tests/ -v
```

Expected: All tests PASS.

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "security: address findings from security review"
git push
```

---

## pytest.ini

Add this file to the project root so pytest handles async tests correctly:

```ini
[pytest]
asyncio_mode = auto
```

Create it before running any tests:

```bash
echo "[pytest]
asyncio_mode = auto" > pytest.ini
git add pytest.ini
git commit -m "chore: configure pytest-asyncio auto mode"
```
