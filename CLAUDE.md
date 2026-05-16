# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

All commands use `uv` for the Python environment.

```bash
# Run the dev server
uv run fastapi dev app/main.py

# Run all tests
uv run pytest

# Run a single test file
uv run pytest tests/test_download.py

# Run a single test by name
uv run pytest tests/test_download.py::test_download_returns_zip_with_sources

# Create the first admin user (run once after deployment)
uv run python create_admin.py <username> <password>
```

## Architecture

This is a FastAPI web app that lets authenticated users download contest submissions from a DMOJ instance as a ZIP archive.

**Request flow for `/download`:**
1. Auth check via session cookie (`app/auth.py`)
2. Validate slug with regex
3. `DMOJClient` (async context manager in `app/dmoj_client.py`) fetches contest participants, then paginates through all submissions, then fetches all source files concurrently (semaphore-limited to 20)
4. `stream_contest_zip` in `app/zip_builder.py` streams the ZIP back as a `StreamingResponse`

**Key modules:**
- `app/main.py` — FastAPI app, `LoggingMiddleware`, lifespan (`init_db`), and all main routes
- `app/admin.py` — `/admin` router for user CRUD (create, toggle active, reset password)
- `app/dmoj_client.py` — async HTTPX client for the DMOJ API; `ContestNotFoundError` signals 404
- `app/zip_builder.py` — pure functions: `sanitize_name`, `build_submission_filename`, `stream_contest_zip`
- `app/database.py` — aiosqlite helpers; `DB_PATH` is a module-level string that tests monkeypatch
- `app/auth.py` — bcrypt authentication + session-based `get_current_user`
- `app/config.py` — reads env vars; all required vars raise `KeyError` on startup if missing

**ZIP structure:** `{sanitized_username}/{sanitized_problem}/{index}_{username}_{date}_{time}_{verdict}.{ext}`

Submissions where source fetch fails are silently dropped (indices renumber from the remaining ones only).

**Auth:** Session cookies via `itsdangerous`/`SessionMiddleware`. Sessions last 8 hours. `HTTPS_ONLY=true` sets `Secure` on cookies.

## Environment

Copy `.env.example` to `.env`. Required vars: `DMOJ_BASE_URL`, `DMOJ_API_TOKEN`, `SECRET_KEY`. Optional: `LOG_LEVEL` (default `INFO`), `HTTPS_ONLY` (default `true`).

## Testing conventions

Tests use `pytest-asyncio` (mode: auto) and `respx` for mocking HTTPX calls. Each test file that hits the database uses a unique `TEST_DB` filename and monkeypatches `app.database.DB_PATH` so tests don't share state. The app is tested via `httpx.AsyncClient` with `ASGITransport`.
