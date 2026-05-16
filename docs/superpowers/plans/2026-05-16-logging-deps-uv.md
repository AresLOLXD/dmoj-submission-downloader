# Logging, Dependency Updates & uv Migration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add structured logging across all app modules, update all dependencies to latest stable, and migrate from `requirements.txt` to `uv` / `pyproject.toml`.

**Architecture:** Task 1 and Task 2 are fully independent — no shared files. They can be dispatched in parallel. Task 1 owns `pyproject.toml`, `requirements.txt`, `pytest.ini`, `README.md`. Task 2 owns `app/logging_config.py` and adds loggers to existing app modules.

**Tech Stack:** Python 3.11+, FastAPI, stdlib `logging`, uv (Astral), pytest + caplog

**Subagents:**
- Task 1 → `voltagent-dev-exp:dependency-manager`
- Task 2 → `voltagent-lang:fastapi-developer`

---

## Task 1: uv Migration + Dependency Updates

**Subagent:** `voltagent-dev-exp:dependency-manager`

**Files:**
- Create: `pyproject.toml`
- Modify: `pytest.ini`
- Modify: `README.md`
- Delete: `requirements.txt`
- Generated: `uv.lock` (by `uv sync`)

---

- [ ] **Step 1: Install uv**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Verify:
```bash
uv --version
```
Expected: `uv 0.x.x` (any recent version)

---

- [ ] **Step 2: Create pyproject.toml**

Create `pyproject.toml` at the project root with the following content:

```toml
[project]
name = "dmoj-downloader"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.136.1",
    "uvicorn[standard]>=0.47.0",
    "jinja2>=3.1.5",
    "httpx>=0.28.1",
    "aiosqlite>=0.21.0",
    "bcrypt>=5.0.0",
    "itsdangerous>=2.2.0",
    "zipstream-new>=1.1.8",
    "python-multipart>=0.0.20",
    "python-dotenv>=1.1.0",
]

[dependency-groups]
dev = [
    "pytest>=9.0.3",
    "pytest-asyncio>=1.3.0",
    "respx>=0.22.0",
]
```

---

- [ ] **Step 3: Install dependencies with uv**

```bash
uv sync --dev
```

Expected: uv creates/updates `.venv` and generates `uv.lock`. No errors.

---

- [ ] **Step 4: Run the full test suite**

```bash
uv run pytest -v
```

Expected: all tests pass. If any fail, read the failure message carefully before continuing. Common issues:

- **`bcrypt` 5.x:** API for `hashpw`/`checkpw` is unchanged — no fixes needed.
- **`pytest-asyncio` 1.x `DeprecationWarning` about `asyncio_default_fixture_loop_scope`:** Fix in Step 5.
- **Any other failure:** fix before proceeding.

---

- [ ] **Step 5: Fix pytest-asyncio 1.x warning in pytest.ini**

Open `pytest.ini`. Its current content is:

```ini
[pytest]
asyncio_mode = auto
```

Update it to:

```ini
[pytest]
asyncio_mode = auto
asyncio_default_fixture_loop_scope = function
```

---

- [ ] **Step 6: Run tests again to confirm clean output**

```bash
uv run pytest -v
```

Expected: all tests pass, no `DeprecationWarning` about `asyncio_default_fixture_loop_scope`.

---

- [ ] **Step 7: Delete requirements.txt**

```bash
rm requirements.txt
```

---

- [ ] **Step 8: Update README.md setup instructions**

Find and replace the **"2. Crear entorno virtual"** and **"3. Instalar dependencias"** sections in `README.md`:

Replace:
```markdown
### 2. Crear entorno virtual

```bash
python3 -m venv .venv
source .venv/bin/activate
```

En Windows:
```cmd
python -m venv .venv
.venv\Scripts\activate
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```
```

With:
```markdown
### 2. Instalar dependencias

Requiere [uv](https://docs.astral.sh/uv/getting-started/installation/).

```bash
uv sync --dev
```
```

Also update the **"Paso 2: Clonar y configurar"** production section. Replace:

```markdown
# Crear entorno virtual
python3.11 -m venv .venv
source .venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt
```

With:

```markdown
# Instalar dependencias (requiere uv)
uv sync
```

Also update the **"Ejecutar el servidor"** development section. Replace:

```markdown
```bash
source .venv/bin/activate
python3 -m uvicorn app.main:app --reload
```
```

With:

```markdown
```bash
uv run uvicorn app.main:app --reload
```
```

Also update the **"Ejecutar el servidor"** part under development. Find any remaining `pip install` references and replace with `uv sync`. Find any remaining `python3 -m pytest` references and replace with `uv run pytest`.

---

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml uv.lock pytest.ini README.md
git commit -m "chore: migrate to uv, update all dependencies to latest"
```

---

## Task 2: Logging System

**Subagent:** `voltagent-lang:fastapi-developer`

**Files:**
- Create: `app/logging_config.py`
- Modify: `app/config.py` — add `LOG_LEVEL`
- Modify: `.env.example` — add `LOG_LEVEL=INFO`
- Modify: `app/main.py` — wire logging, add `LoggingMiddleware`, add download log events, add logout log
- Modify: `app/auth.py` — add logger, log login events
- Modify: `app/admin.py` — add logger, log admin events
- Modify: `tests/test_auth.py` — add caplog assertions
- Modify: `tests/test_admin.py` — add caplog assertions
- Modify: `tests/test_download.py` — add caplog assertions

---

### 2a — logging_config + config wiring

- [ ] **Step 1: Write a failing test for configure_logging**

Add a new file `tests/test_logging_config.py`:

```python
import logging
from app.logging_config import configure_logging


def test_configure_logging_sets_root_level_to_debug():
    configure_logging("DEBUG")
    assert logging.getLogger().level == logging.DEBUG


def test_configure_logging_sets_root_level_to_info():
    configure_logging("INFO")
    assert logging.getLogger().level == logging.INFO
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
pytest tests/test_logging_config.py -v
```

Expected: `ImportError: cannot import name 'configure_logging' from 'app.logging_config'` (module doesn't exist yet).

- [ ] **Step 3: Create app/logging_config.py**

```python
import logging


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=level,
        format="%(levelname)-8s %(asctime)s %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
```

- [ ] **Step 4: Run test to confirm it passes**

```bash
pytest tests/test_logging_config.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Add LOG_LEVEL to app/config.py**

The current end of `app/config.py` is:

```python
HTTPS_ONLY: bool = os.environ.get("HTTPS_ONLY", "true").lower() != "false"
```

Add after it:

```python
LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO").upper()
```

- [ ] **Step 6: Add LOG_LEVEL to .env.example**

The current `.env.example` content is:

```
DMOJ_BASE_URL=https://your-dmoj-instance.com
DMOJ_API_TOKEN=your_api_token
SECRET_KEY=your_secret_key
HTTPS_ONLY=true
```

Add at the end:

```
LOG_LEVEL=INFO
```

- [ ] **Step 7: Wire configure_logging in app/main.py**

At the top of `app/main.py`, the current imports end with:

```python
from app.zip_builder import sanitize_name, stream_contest_zip
```

Add after that line:

```python
from app.logging_config import configure_logging

configure_logging(config.LOG_LEVEL)
logger = logging.getLogger(__name__)
```

And add `import logging` to the existing imports at the top of the file (after `import re`):

```python
import logging
```

- [ ] **Step 8: Commit**

```bash
git add app/logging_config.py app/config.py app/.env.example app/main.py tests/test_logging_config.py
git commit -m "feat: add logging_config module and LOG_LEVEL config"
```

---

### 2b — HTTP request logging middleware

- [ ] **Step 9: Write a failing test for the middleware**

Add a new file `tests/test_middleware.py`:

```python
import logging
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_middleware_logs_http_request(caplog):
    with caplog.at_level(logging.INFO, logger="app.main"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client:
            await client.get("/health")
    assert any(
        "GET" in r.message and "/health" in r.message and "status=200" in r.message
        for r in caplog.records
    )
```

- [ ] **Step 10: Run test to confirm it fails**

```bash
pytest tests/test_middleware.py -v
```

Expected: FAIL — no matching log record.

- [ ] **Step 11: Add LoggingMiddleware to app/main.py**

Add the following imports at the top of `app/main.py`, after `import logging`:

```python
import time
from starlette.types import ASGIApp, Receive, Scope, Send
```

Add the `LoggingMiddleware` class before the `app = FastAPI()` line:

```python
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
```

Then add `app.add_middleware(LoggingMiddleware)` **after** the existing `app.add_middleware(SessionMiddleware, ...)` call, so the logging middleware is outermost:

```python
app.add_middleware(
    SessionMiddleware,
    secret_key=config.SECRET_KEY,
    max_age=28800,
    https_only=config.HTTPS_ONLY,
    same_site="strict",
)
app.add_middleware(LoggingMiddleware)
```

- [ ] **Step 12: Run test to confirm it passes**

```bash
pytest tests/test_middleware.py -v
```

Expected: 1 passed.

- [ ] **Step 13: Run full test suite to check for regressions**

```bash
pytest -v
```

Expected: all existing tests still pass.

- [ ] **Step 14: Commit**

```bash
git add app/main.py tests/test_middleware.py
git commit -m "feat: add HTTP request logging middleware"
```

---

### 2c — Auth logging

- [ ] **Step 15: Write failing tests for auth logging**

Append to `tests/test_auth.py`:

```python
@pytest.mark.asyncio
async def test_login_success_logs_info(caplog):
    import logging
    with caplog.at_level(logging.INFO, logger="app.auth"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client:
            await client.post("/login", data={"username": "delegate1", "password": "secret"})
    assert any(
        "login_ok" in r.message and "delegate1" in r.message
        for r in caplog.records
    )


@pytest.mark.asyncio
async def test_login_failure_logs_warning(caplog):
    import logging
    with caplog.at_level(logging.WARNING, logger="app.auth"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client:
            await client.post("/login", data={"username": "delegate1", "password": "wrong"})
    assert any(
        "login_failed" in r.message and "delegate1" in r.message
        for r in caplog.records
    )
```

- [ ] **Step 16: Run new tests to confirm they fail**

```bash
pytest tests/test_auth.py::test_login_success_logs_info tests/test_auth.py::test_login_failure_logs_warning -v
```

Expected: 2 FAIL — no matching log records.

- [ ] **Step 17: Add logger to app/auth.py**

Add after the existing imports in `app/auth.py`:

```python
import logging

logger = logging.getLogger(__name__)
```

In the `authenticate` function, add logging after the final `return None` / `return user`. The current function ends with:

```python
async def authenticate(username: str, password: str) -> Optional[User]:
    async with aiosqlite.connect(database.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        user = await get_user_by_username(db, username)
    check_hash = user.password_hash if (user and user.is_active) else _DUMMY_HASH
    if not bcrypt.checkpw(password.encode(), check_hash.encode()):
        return None
    if user is None or not user.is_active:
        return None
    return user
```

Replace with:

```python
async def authenticate(username: str, password: str) -> Optional[User]:
    async with aiosqlite.connect(database.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        user = await get_user_by_username(db, username)
    check_hash = user.password_hash if (user and user.is_active) else _DUMMY_HASH
    if not bcrypt.checkpw(password.encode(), check_hash.encode()):
        logger.warning("login_failed user=%s", username)
        return None
    if user is None or not user.is_active:
        logger.warning("login_failed user=%s", username)
        return None
    logger.info("login_ok user=%s", username)
    return user
```

- [ ] **Step 18: Run tests to confirm they pass**

```bash
pytest tests/test_auth.py -v
```

Expected: all tests pass, including the 2 new ones.

- [ ] **Step 19: Add logout logging to app/main.py**

The current logout handler in `app/main.py` is:

```python
@app.post("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)
```

Replace with:

```python
@app.post("/logout")
async def logout(request: Request):
    user = await get_current_user(request)
    if user:
        logger.info("logout user=%s", user.username)
    request.session.clear()
    return RedirectResponse("/login", status_code=303)
```

- [ ] **Step 20: Run full test suite**

```bash
pytest -v
```

Expected: all tests pass.

- [ ] **Step 21: Commit**

```bash
git add app/auth.py app/main.py tests/test_auth.py
git commit -m "feat: add login/logout logging to auth module"
```

---

### 2d — Admin logging

- [ ] **Step 22: Write failing tests for admin logging**

Append to `tests/test_admin.py`:

```python
@pytest.mark.asyncio
async def test_create_user_logs_info(caplog):
    import logging
    with caplog.at_level(logging.INFO, logger="app.admin"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client:
            await client.post("/login", data={"username": "admin1", "password": "adminpass"})
            await client.post("/admin/users", data={"username": "newuser", "password": "pw"})
    assert any(
        "user_created" in r.message and "admin1" in r.message and "newuser" in r.message
        for r in caplog.records
    )


@pytest.mark.asyncio
async def test_toggle_user_logs_info(caplog):
    import logging
    with caplog.at_level(logging.INFO, logger="app.admin"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client:
            await client.post("/login", data={"username": "admin1", "password": "adminpass"})
            # delegate1 is user id=2 in test DB
            async with aiosqlite.connect(TEST_DB) as db:
                db.row_factory = aiosqlite.Row
                from app.database import get_user_by_username
                target = await get_user_by_username(db, "delegate1")
            await client.post(f"/admin/users/{target.id}/toggle")
    assert any("user_toggled" in r.message and "admin1" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_reset_password_logs_info(caplog):
    import logging
    with caplog.at_level(logging.INFO, logger="app.admin"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client:
            await client.post("/login", data={"username": "admin1", "password": "adminpass"})
            async with aiosqlite.connect(TEST_DB) as db:
                db.row_factory = aiosqlite.Row
                from app.database import get_user_by_username
                target = await get_user_by_username(db, "delegate1")
            await client.post(f"/admin/users/{target.id}/reset-password", data={"new_password": "newpw"})
    assert any("password_reset" in r.message and "admin1" in r.message for r in caplog.records)
```

- [ ] **Step 23: Run new tests to confirm they fail**

```bash
pytest tests/test_admin.py::test_create_user_logs_info tests/test_admin.py::test_toggle_user_logs_info tests/test_admin.py::test_reset_password_logs_info -v
```

Expected: 3 FAIL.

- [ ] **Step 24: Add logger to app/admin.py**

Add after the existing imports:

```python
import logging

logger = logging.getLogger(__name__)
```

In `create_user_route`, add logging before the redirect. The current handler ends with:

```python
    async with aiosqlite.connect(database.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await create_user(db, username, hashed, is_admin=bool(is_admin))
    return RedirectResponse("/admin", status_code=303)
```

Replace the last two lines with:

```python
    async with aiosqlite.connect(database.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await create_user(db, username, hashed, is_admin=bool(is_admin))
    logger.info("user_created admin=%s username=%s", user.username, username)
    return RedirectResponse("/admin", status_code=303)
```

In `toggle_user_active`, add logging before the redirect. The current handler ends with:

```python
    async with aiosqlite.connect(database.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        target = await get_user_by_id(db, user_id)
        if target:
            await set_user_active(db, user_id, not target.is_active)
    return RedirectResponse("/admin", status_code=303)
```

Replace with:

```python
    async with aiosqlite.connect(database.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        target = await get_user_by_id(db, user_id)
        if target:
            new_active = not target.is_active
            await set_user_active(db, user_id, new_active)
            logger.info("user_toggled admin=%s target=%s active=%s", user.username, user_id, new_active)
    return RedirectResponse("/admin", status_code=303)
```

In `reset_password_route`, add logging before the redirect. The current handler ends with:

```python
    hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    async with aiosqlite.connect(database.DB_PATH) as db:
        await update_password(db, user_id, hashed)
    return RedirectResponse("/admin", status_code=303)
```

Replace with:

```python
    hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    async with aiosqlite.connect(database.DB_PATH) as db:
        await update_password(db, user_id, hashed)
    logger.info("password_reset admin=%s target=%s", user.username, user_id)
    return RedirectResponse("/admin", status_code=303)
```

- [ ] **Step 25: Run tests to confirm they pass**

```bash
pytest tests/test_admin.py -v
```

Expected: all tests pass.

- [ ] **Step 26: Commit**

```bash
git add app/admin.py tests/test_admin.py
git commit -m "feat: add admin action logging"
```

---

### 2e — Download log events

- [ ] **Step 27: Write failing tests for download logging**

Append to `tests/test_download.py`:

```python
@pytest.mark.asyncio
async def test_download_start_and_done_logged(caplog):
    import logging
    with respx.mock:
        respx.get(f"{BASE}/api/v2/contest/ioi2025").mock(return_value=httpx.Response(200, json={
            "data": {"object": {"key": "ioi2025", "rankings": [{"user": "alice"}]}}
        }))
        respx.get(f"{BASE}/api/v2/submissions").mock(return_value=httpx.Response(200, json={
            "data": {
                "objects": [
                    {"id": 1, "user": "alice", "problem": "prob_a", "result": "AC",
                     "language": "PY3", "date": "2025-05-15T14:30:22+00:00"},
                ],
                "has_more": False,
            }
        }))
        respx.get(f"{BASE}/src/1/raw").mock(return_value=httpx.Response(200, text="print('hi')"))

        with caplog.at_level(logging.INFO, logger="app.main"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client:
                await client.post("/login", data={"username": "user1", "password": "pass"})
                await client.get("/download?slug=ioi2025")

    assert any("download_start" in r.message and "ioi2025" in r.message for r in caplog.records)
    assert any("download_done" in r.message and "ioi2025" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_download_invalid_slug_logs_warning(caplog):
    import logging
    with caplog.at_level(logging.WARNING, logger="app.main"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client:
            await client.post("/login", data={"username": "user1", "password": "pass"})
            await client.get("/download?slug=bad slug!")
    assert any("download_invalid_slug" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_download_not_found_logs_warning(caplog):
    import logging
    with respx.mock:
        respx.get(f"{BASE}/api/v2/contest/nope").mock(return_value=httpx.Response(404))
        with caplog.at_level(logging.WARNING, logger="app.main"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client:
                await client.post("/login", data={"username": "user1", "password": "pass"})
                await client.get("/download?slug=nope")
    assert any("download_not_found" in r.message and "nope" in r.message for r in caplog.records)
```

- [ ] **Step 28: Run new tests to confirm they fail**

```bash
pytest tests/test_download.py::test_download_start_and_done_logged tests/test_download.py::test_download_invalid_slug_logs_warning tests/test_download.py::test_download_not_found_logs_warning -v
```

Expected: 3 FAIL.

- [ ] **Step 29: Add download log events to app/main.py**

In the `download` handler, add `import time` is already at the top (added in Step 11). Now modify the download handler. The current handler body (after the auth check) is:

```python
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
```

Replace with:

```python
    if not re.fullmatch(r"[a-zA-Z0-9_\-]{1,64}", slug):
        logger.warning("download_invalid_slug slug=%s user=%s", slug, user.username)
        return templates.TemplateResponse(
            request,
            "dashboard.html",
            {"user": user, "error": "Slug inválido. Solo se permiten letras, números, guiones y guiones bajos."},
        )

    logger.info("download_start slug=%s user=%s", slug, user.username)
    _download_start = time.monotonic()
    async with DMOJClient(base_url=config.DMOJ_BASE_URL, token=config.DMOJ_API_TOKEN) as dmoj:
        try:
            await dmoj.get_contest_participants(slug)
        except ContestNotFoundError:
            logger.warning("download_not_found slug=%s user=%s", slug, user.username)
            return templates.TemplateResponse(
                request,
                "dashboard.html",
                {"user": user, "error": f"Concurso '{slug}' no encontrado."},
            )

        submissions = await dmoj.get_contest_submissions(slug)
        sources = await dmoj.get_all_sources([sub["id"] for sub in submissions])
```

Then find the line just before `headers: dict[str, str] = ...` (after the `subs.append(...)` loop closes):

```python
    headers: dict[str, str] = {"Content-Disposition": ...}
```

Add the log line before it:

```python
    logger.info(
        "download_done slug=%s submissions=%d duration=%.2fs",
        slug,
        len(subs),
        time.monotonic() - _download_start,
    )
    headers: dict[str, str] = {"Content-Disposition": f'attachment; filename="{sanitize_name(slug)}.zip"'}
```

- [ ] **Step 30: Run new tests to confirm they pass**

```bash
pytest tests/test_download.py -v
```

Expected: all tests pass.

- [ ] **Step 31: Run full test suite**

```bash
pytest -v
```

Expected: all tests pass, no warnings.

- [ ] **Step 32: Commit**

```bash
git add app/main.py tests/test_download.py
git commit -m "feat: add download event logging to main handler"
```
