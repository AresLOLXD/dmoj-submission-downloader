# DMOJ Submission Downloader — Design Spec

**Date:** 2026-05-15

## Overview

A web application hosted on a personal server that allows delegates and advisors from across the country to download all contest submissions from a self-hosted DMOJ instance, packaged as a structured ZIP file.

---

## Requirements

- Authenticated access only — no public registration, admin creates accounts
- Single DMOJ API token stored server-side (delegates never see it)
- User inputs a contest slug manually to trigger a download
- Downloads ALL submissions per contestant per problem (not just the best/last)
- ZIP generated via streaming to minimize RAM usage
- Admin panel to manage users (create, activate, deactivate, reset password)

---

## Architecture

```
Caddy (reverse proxy + automatic TLS)
    │
FastAPI + Uvicorn (systemd service, localhost:8000)
    ├── Auth routes       /login  /logout
    ├── Dashboard route   /dashboard
    ├── Download route    /download/{slug}
    └── Admin routes      /admin/*

SQLite (users + sessions)
.env  (DMOJ_API_TOKEN, DMOJ_BASE_URL, SECRET_KEY)
```

**Key libraries:**
- `fastapi` + `uvicorn` — ASGI server
- `jinja2` — server-side HTML templates
- `tailwindcss` (CDN) — styling
- `httpx` — async HTTP client for DMOJ API
- `aiosqlite` — async SQLite access
- `bcrypt` — password hashing
- `itsdangerous` — signed session cookies
- `zipstream-new` — streaming ZIP generation

---

## Project Structure

```
dmoj-downloader/
├── main.py              # FastAPI app, route definitions
├── auth.py              # Session management, login/logout, route guards
├── dmoj_client.py       # httpx client wrapping DMOJ API calls
├── zip_builder.py       # Streaming ZIP generator
├── database.py          # SQLite connection and queries (aiosqlite)
├── models.py            # Data models (User, Submission, etc.)
├── templates/
│   ├── login.html
│   ├── dashboard.html
│   └── admin.html
├── create_admin.py      # CLI script to bootstrap the first admin user
├── .env                 # Secrets (not committed)
├── .env.example         # Template for .env
├── requirements.txt
├── Caddyfile
└── dmoj-downloader.service  # systemd unit file
```

---

## Data Model

```sql
CREATE TABLE users (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    username     TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,       -- bcrypt
    is_admin     BOOLEAN NOT NULL DEFAULT 0,
    is_active    BOOLEAN NOT NULL DEFAULT 1,
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

Sessions are stored in signed cookies (no server-side session table).

---

## Data Flow — Download

1. Authenticated user submits contest slug via form on `/dashboard`
2. FastAPI calls `GET {DMOJ_BASE_URL}/api/v2/contest/{slug}` to validate and get participant list
3. FastAPI calls `GET {DMOJ_BASE_URL}/api/v2/contest/{slug}/submissions` to get all submission IDs
4. For each submission, `GET {DMOJ_BASE_URL}/api/v2/submission/{id}` fetches source code
5. Each file is written chunk-by-chunk into a `zipstream` generator
6. FastAPI returns a `StreamingResponse` — ZIP is sent to the browser as it's built
7. RAM usage at any moment: approximately one submission's source code, not the full ZIP

---

## ZIP Structure

```
{contest-slug}.zip
└── {sanitized_username}/
    └── {problem_code}/
        ├── 1_{username}_{YYYY-MM-DD}_{HH-MM-SS}_{verdict}.{ext}
        ├── 2_{username}_{YYYY-MM-DD}_{HH-MM-SS}_{verdict}.{ext}
        └── 3_{username}_{YYYY-MM-DD}_{HH-MM-SS}_{verdict}.{ext}
```

**Filename sanitization:** Any character outside `[a-zA-Z0-9_-]` is replaced with `_`. Maximum path component length: 64 characters.

Example filename: `1_usuario123_2025-05-15_14-30-22_AC.py`

---

## Authentication & Admin Panel

- No public registration — admin creates all accounts
- First admin created via `python create_admin.py` CLI script
- Login: username + password → signed session cookie
- Sessions expire after 8 hours of inactivity

**Admin panel** (`/admin`, requires `is_admin=True`):
- List all users with status and creation date
- Create new user (username + temporary password)
- Activate / deactivate user (revokes access without deleting account)
- Reset any user's password

---

## Error Handling

| Situation | Behavior |
|---|---|
| Invalid contest slug | Error message on dashboard, no download starts |
| DMOJ API token invalid/expired | 500 error with clear message to user |
| Contest has no participants or submissions | ZIP is empty; user sees informative message |
| DMOJ API timeout | 30s timeout per request; error shown to user |
| Download interrupted by user | Stream closes cleanly; no server-side side effects |
| Concurrent downloads by different users | Each request is fully independent — no shared state |
| Username with special characters | Sanitized before use in ZIP paths |

No automatic retries — if the DMOJ API fails mid-stream, the user receives an incomplete ZIP and must retry manually.

---

## Deployment

**systemd service:** Uvicorn runs as a service on `localhost:8000`.

**Caddyfile (example):**
```
your-domain.com {
    reverse_proxy localhost:8000
}
```

**Environment variables (`.env`):**
```
DMOJ_BASE_URL=https://your-dmoj-instance.com
DMOJ_API_TOKEN=your_token_here
SECRET_KEY=a_long_random_string_for_signing_sessions
```

Caddy handles TLS automatically via Let's Encrypt.
