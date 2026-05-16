# Loading Screen Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix security and robustness issues found in the code review of the loading modal feature.

**Architecture:** Two independent fixes — server-side token validation + `Secure` cookie flag in `app/main.py`, and frontend timeout fallback + robust cookie parsing in `templates/dashboard.html`. No new files needed.

**Tech Stack:** FastAPI, Python 3.11+, vanilla JS, Tailwind CSS, pytest + respx for tests.

---

## Context

The base loading screen was already implemented. These tasks fix the issues found in code review:

| Severity | Issue |
|----------|-------|
| Critical | Token reflected into `Set-Cookie` without validation — header injection via `\r\n` |
| Critical | Modal stays stuck forever if server never sets the cookie (network failure, server crash) |
| Warning  | Cookie lacks `Secure` flag when `HTTPS_ONLY=True` |
| Warning  | Cookie polling uses exact string match, brittle against encoding or prefix collisions |

---

## Files

- Modify: `app/main.py` — token validation + Secure flag
- Modify: `templates/dashboard.html` — timeout fallback + robust cookie parsing
- Modify: `tests/test_download.py` — tests for token validation and cookie header

---

## Task 1: Server-side token validation and Secure cookie flag

**Files:**
- Modify: `app/main.py`
- Modify: `tests/test_download.py`

Current state of the `/download` endpoint signature and cookie logic (lines 69–130 of `app/main.py`):

```python
@app.get("/download")
async def download(request: Request, slug: str, token: str | None = None):
    ...
    headers: dict[str, str] = {"Content-Disposition": f'attachment; filename="{sanitize_name(slug)}.zip"'}
    if token is not None:
        headers["Set-Cookie"] = f"download_ready={token}; Path=/; SameSite=Strict"
    return StreamingResponse(
        stream_contest_zip(iter(subs)),
        media_type="application/zip",
        headers=headers,
    )
```

- [ ] **Step 1: Write failing tests for token validation**

Add these tests to `tests/test_download.py`:

```python
@pytest.mark.asyncio
async def test_download_sets_cookie_when_valid_token_provided():
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
                "has_more": False
            }
        }))
        respx.get(f"{BASE}/src/1/raw").mock(return_value=httpx.Response(200, text="print('hi')"))

        async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client:
            await client.post("/login", data={"username": "user1", "password": "pass"})
            response = await client.get("/download?slug=ioi2025&token=abc12345")

    assert response.status_code == 200
    cookie_header = response.headers.get("set-cookie", "")
    assert "download_ready=abc12345" in cookie_header


@pytest.mark.asyncio
async def test_download_ignores_invalid_token():
    with respx.mock:
        respx.get(f"{BASE}/api/v2/contest/ioi2025").mock(return_value=httpx.Response(200, json={
            "data": {"object": {"key": "ioi2025", "rankings": [{"user": "alice"}]}}
        }))
        respx.get(f"{BASE}/api/v2/submissions").mock(return_value=httpx.Response(200, json={
            "data": {"objects": [], "has_more": False}
        }))

        async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client:
            await client.post("/login", data={"username": "user1", "password": "pass"})
            response = await client.get("/download?slug=ioi2025&token=bad%0d%0atoken")

    assert response.status_code == 200
    cookie_header = response.headers.get("set-cookie", "")
    assert "download_ready" not in cookie_header
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /opt/dmoj-downloader
pytest tests/test_download.py::test_download_sets_cookie_when_valid_token_provided tests/test_download.py::test_download_ignores_invalid_token -v
```

Expected: first test FAILS (no `set-cookie` header currently), second test behavior is undefined.

- [ ] **Step 3: Add `re` import if not already present and update the download endpoint**

`re` is already imported at the top of `app/main.py`. Update the cookie block at the end of the `/download` endpoint (replace the existing `if token is not None` block):

```python
    headers: dict[str, str] = {"Content-Disposition": f'attachment; filename="{sanitize_name(slug)}.zip"'}
    if token is not None and re.fullmatch(r"[a-zA-Z0-9\-]{1,64}", token):
        cookie = f"download_ready={token}; Path=/; SameSite=Strict"
        if config.HTTPS_ONLY:
            cookie += "; Secure"
        headers["Set-Cookie"] = cookie
    return StreamingResponse(
        stream_contest_zip(iter(subs)),
        media_type="application/zip",
        headers=headers,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_download.py::test_download_sets_cookie_when_valid_token_provided tests/test_download.py::test_download_ignores_invalid_token -v
```

Expected: both PASS.

- [ ] **Step 5: Run full test suite to verify no regressions**

```bash
pytest tests/test_download.py -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add app/main.py tests/test_download.py
git commit -m "fix: validate token before reflecting into Set-Cookie, add Secure flag"
```

---

## Task 2: Frontend — timeout fallback and robust cookie parsing

**Files:**
- Modify: `templates/dashboard.html`

Current JS block in `templates/dashboard.html` (lines 37–61):

```html
<script>
(function () {
    const form = document.querySelector('form[action="/download"]');
    const modal = document.getElementById('loading-modal');

    form.addEventListener('submit', function (e) {
        e.preventDefault();
        const slug = form.querySelector('input[name="slug"]').value;
        const token = crypto.randomUUID().slice(0, 8);
        modal.style.display = 'flex';

        const interval = setInterval(function () {
            if (document.cookie.split(';').some(function (c) {
                return c.trim() === 'download_ready=' + token;
            })) {
                clearInterval(interval);
                document.cookie = 'download_ready=; Max-Age=0; Path=/';
                modal.style.display = 'none';
            }
        }, 500);

        window.location.href = '/download?slug=' + encodeURIComponent(slug) + '&token=' + token;
    });
}());
</script>
```

- [ ] **Step 1: Replace the `<script>` block in `templates/dashboard.html`**

Replace the entire `<script>...</script>` block (lines 37–61) with:

```html
<script>
(function () {
    const form = document.querySelector('form[action="/download"]');
    const modal = document.getElementById('loading-modal');

    function getCookie(name) {
        return document.cookie.split(';').some(function (c) {
            const [k, v] = c.trim().split('=');
            return k === name && v !== undefined;
        });
    }

    function dismissModal(interval, timeout) {
        clearInterval(interval);
        clearTimeout(timeout);
        document.cookie = 'download_ready=; Max-Age=0; Path=/';
        modal.style.display = 'none';
    }

    form.addEventListener('submit', function (e) {
        e.preventDefault();
        const slug = form.querySelector('input[name="slug"]').value;
        const token = crypto.randomUUID().replace(/-/g, '').slice(0, 8);
        modal.style.display = 'flex';

        let interval;
        const timeout = setTimeout(function () {
            dismissModal(interval, timeout);
        }, 60000);

        interval = setInterval(function () {
            if (getCookie('download_ready')) {
                dismissModal(interval, timeout);
            }
        }, 500);

        window.location.href = '/download?slug=' + encodeURIComponent(slug) + '&token=' + token;
    });

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && modal.style.display !== 'none') {
            modal.style.display = 'none';
        }
    });
}());
</script>
```

Changes made:
- `getCookie` parses name/value explicitly instead of exact string match.
- Token generation uses `.replace(/-/g, '')` to strip hyphens before slicing, ensuring 8 alphanumeric chars that match the server regex `[a-zA-Z0-9\-]{1,64}`.
- `dismissModal` centralizes cleanup of both interval and timeout.
- `setTimeout` of 60s auto-dismisses the modal as fallback.
- `keydown` listener on `Escape` allows manual dismissal.

- [ ] **Step 2: Commit**

```bash
git add templates/dashboard.html
git commit -m "fix: add timeout fallback, robust cookie parsing, and ESC dismiss to loading modal"
```

---

## Verification

After both tasks are complete:

```bash
pytest -v
```

Expected: all tests PASS, no regressions.
