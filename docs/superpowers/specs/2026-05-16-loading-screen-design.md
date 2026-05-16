# Loading Screen During ZIP Download

**Date:** 2026-05-16
**Status:** Approved

## Overview

Show a modal overlay while the server builds and begins streaming the ZIP file. The modal dismisses automatically once the download starts, using a cookie-based polling mechanism.

## Flow

1. User submits the download form (slug input).
2. JS intercepts the submit event.
3. JS generates a short random token (e.g. 8 hex chars via `crypto.randomUUID()`).
4. JS shows the loading modal.
5. JS navigates to `/download?slug=<slug>&token=<token>` via `window.location.href`.
6. Server processes the request (fetches submissions, builds ZIP structure).
7. Before streaming the response, server sets `Set-Cookie: download_ready=<token>; Path=/; SameSite=Strict`.
8. JS polls `document.cookie` every 500ms looking for `download_ready=<token>`.
9. When found, JS deletes the cookie and hides the modal.

## Backend Changes (`app/main.py`)

- Read optional `token: str | None` query param in the `/download` endpoint.
- Before returning the `StreamingResponse`, wrap it to set the cookie header if a token was provided.
- Use `response.set_cookie(key="download_ready", value=token)` on a `Response` object passed to `StreamingResponse` headers, or inject via `headers={"Set-Cookie": f"download_ready={token}; Path=/; SameSite=Strict"}`.

## Frontend Changes (`templates/dashboard.html`)

### Modal HTML
Appended before `{% endblock %}`:
- Fixed full-screen overlay (`position: fixed; inset: 0`) with `bg-black/50` backdrop.
- Centered card with CSS spinner + "Preparando descarga..." text.
- Hidden by default (`display: none`), shown on submit.

### JavaScript
- Intercept `form.addEventListener("submit", ...)`.
- `event.preventDefault()`.
- Generate token with `crypto.randomUUID().slice(0, 8)`.
- Show modal.
- Set `window.location.href` to `/download?slug=<slug>&token=<token>`.
- Start polling: `setInterval` every 500ms checking `document.cookie` for `download_ready=<token>`.
- On match: clear interval, delete cookie (`document.cookie = "download_ready=; Max-Age=0; Path=/"`), hide modal.

## Error Handling

- If the server returns an error (invalid slug, contest not found), it renders `dashboard.html` again — the page reload naturally dismisses the modal.
- No timeout fallback needed: error responses cause a full page navigation, so the modal disappears.

## Scope

- No changes to `zip_builder.py`, `dmoj_client.py`, or other files.
- Two files touched: `app/main.py` and `templates/dashboard.html`.
