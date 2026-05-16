# Bug Fixes: Source Fetching & Download Performance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix three bugs: source fetching always fails (uses wrong API endpoint), index counter has gaps when submissions are skipped, and 700+ submission downloads take minutes due to sequential HTTP requests.

**Architecture:** Replace the `/api/v2/submission/{id}` source call with `/src/{id}/raw` (which works for all languages). Fetch all sources concurrently with `asyncio.Semaphore(20)` + `asyncio.gather`. Move the index counter increment to after a source is confirmed present.

**Tech Stack:** Python 3.11, FastAPI, httpx, asyncio, respx (tests), pytest-asyncio

---

## File Map

- **Modify:** `app/dmoj_client.py` — remove `get_submission_source`, add `get_submission_source_raw` and `get_all_sources`
- **Modify:** `app/main.py` — refactor `/download` handler to use `get_all_sources`, fix counter placement
- **Modify:** `tests/test_dmoj_client.py` — replace test for removed method, add tests for new methods
- **Modify:** `tests/test_download.py` — update mock to use `/src/{id}/raw` instead of `/api/v2/submission/{id}`

---

## Task A: Update `DMOJClient` — new source fetching methods

> **Agent note:** Work only in `app/dmoj_client.py` and `tests/test_dmoj_client.py`. Do not touch `main.py`.

**Files:**
- Modify: `app/dmoj_client.py`
- Modify: `tests/test_dmoj_client.py`

- [ ] **Step 1: Write failing test for `get_submission_source_raw`**

Replace the existing `test_get_submission_source_returns_code` test (which tests the old `get_submission_source` method) with a test for the new method:

```python
# In tests/test_dmoj_client.py — replace test_get_submission_source_returns_code with:

@pytest.mark.asyncio
async def test_get_submission_source_raw_returns_code(make_client):
    with respx.mock:
        respx.get(f"{BASE}/src/42/raw").mock(
            return_value=httpx.Response(200, text="print('hello')")
        )
        async with make_client() as client:
            source = await client.get_submission_source_raw(42)
    assert source == "print('hello')"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /opt/dmoj-downloader
source .venv/bin/activate
pytest tests/test_dmoj_client.py::test_get_submission_source_raw_returns_code -v
```

Expected: `FAILED` — `AttributeError: 'DMOJClient' object has no attribute 'get_submission_source_raw'`

- [ ] **Step 3: Write failing test for `get_all_sources`**

Add this test below the previous one:

```python
@pytest.mark.asyncio
async def test_get_all_sources_returns_dict(make_client):
    with respx.mock:
        respx.get(f"{BASE}/src/1/raw").mock(return_value=httpx.Response(200, text="code_1"))
        respx.get(f"{BASE}/src/2/raw").mock(return_value=httpx.Response(200, text="code_2"))
        respx.get(f"{BASE}/src/3/raw").mock(return_value=httpx.Response(200, text="code_3"))
        async with make_client() as client:
            result = await client.get_all_sources([1, 2, 3])
    assert result == {1: "code_1", 2: "code_2", 3: "code_3"}


@pytest.mark.asyncio
async def test_get_all_sources_omits_failed_submissions(make_client):
    with respx.mock:
        respx.get(f"{BASE}/src/1/raw").mock(return_value=httpx.Response(200, text="code_1"))
        respx.get(f"{BASE}/src/2/raw").mock(return_value=httpx.Response(403))
        async with make_client() as client:
            result = await client.get_all_sources([1, 2])
    assert result == {1: "code_1"}
```

- [ ] **Step 4: Run new tests to verify they fail**

```bash
pytest tests/test_dmoj_client.py::test_get_all_sources_returns_dict tests/test_dmoj_client.py::test_get_all_sources_omits_failed_submissions -v
```

Expected: both `FAILED` — `AttributeError: 'DMOJClient' object has no attribute 'get_all_sources'`

- [ ] **Step 5: Implement the new methods in `dmoj_client.py`**

Replace the existing `get_submission_source` method with the two new methods. The full updated `DMOJClient` class (only showing the changed/added methods — keep everything else as-is):

```python
import asyncio
import httpx
from typing import Any

# ... (LANGUAGE_EXTENSIONS and ContestNotFoundError unchanged) ...

class DMOJClient:
    # ... (__init__, __aenter__, __aexit__, _get_client unchanged) ...
    # ... (get_contest_participants, get_contest_submissions unchanged) ...

    async def get_submission_source_raw(self, submission_id: int) -> str:
        client = self._get_client()
        resp = await client.get(f"{self._base}/src/{submission_id}/raw")
        resp.raise_for_status()
        return resp.text

    async def get_all_sources(
        self, ids: list[int], concurrency: int = 20
    ) -> dict[int, str]:
        sem = asyncio.Semaphore(concurrency)

        async def fetch(submission_id: int) -> tuple[int, str | None]:
            async with sem:
                try:
                    source = await self.get_submission_source_raw(submission_id)
                    return submission_id, source
                except httpx.HTTPStatusError:
                    return submission_id, None

        pairs = await asyncio.gather(*(fetch(i) for i in ids))
        return {sid: src for sid, src in pairs if src is not None}

    @staticmethod
    def language_to_ext(language: str) -> str:
        return LANGUAGE_EXTENSIONS.get(language, "txt")
```

The full file after changes (complete, no placeholders):

```python
import asyncio
import httpx
from typing import Any

LANGUAGE_EXTENSIONS: dict[str, str] = {
    "PY3": "py", "PY2": "py", "CPP17": "cpp", "CPP14": "cpp", "CPP11": "cpp",
    "CPP20": "cpp", "C": "c", "JAVA8": "java", "JAVA11": "java", "JAVA17": "java",
    "KOTLIN": "kt", "RUBY": "rb", "RUST": "rs", "GO": "go", "HS": "hs",
    "JS": "js", "CS": "cs", "PAS": "pas", "D": "d", "SWIFT": "swift",
    "PYPY3": "py", "SCALA": "scala", "LUA": "lua", "PHP": "php",
    "PERL": "pl", "BASH": "sh",
}

class ContestNotFoundError(Exception):
    pass

class DMOJClient:
    def __init__(self, base_url: str, token: str) -> None:
        self._base = base_url
        self._headers = {"Authorization": f"Bearer {token}"}
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "DMOJClient":
        self._client = httpx.AsyncClient(headers=self._headers, timeout=30)
        return self

    async def __aexit__(self, *args: object) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("DMOJClient must be used as an async context manager")
        return self._client

    async def get_contest_participants(self, slug: str) -> list[str]:
        client = self._get_client()
        resp = await client.get(f"{self._base}/api/v2/contest/{slug}")
        if resp.status_code == 404:
            raise ContestNotFoundError(slug)
        resp.raise_for_status()
        rankings = resp.json()["data"]["object"]["rankings"]
        return [r["user"] for r in rankings]

    async def get_contest_submissions(self, slug: str) -> list[dict[str, Any]]:
        client = self._get_client()
        results: list[dict[str, Any]] = []
        params: dict[str, Any] = {"contest": slug, "page_size": 100}
        while True:
            resp = await client.get(f"{self._base}/api/v2/submissions", params=params)
            resp.raise_for_status()
            data = resp.json()["data"]
            results.extend(data["objects"])
            if not data.get("has_more"):
                break
            params["after"] = data["next_page_id"]
        return results

    async def get_submission_source_raw(self, submission_id: int) -> str:
        client = self._get_client()
        resp = await client.get(f"{self._base}/src/{submission_id}/raw")
        resp.raise_for_status()
        return resp.text

    async def get_all_sources(
        self, ids: list[int], concurrency: int = 20
    ) -> dict[int, str]:
        sem = asyncio.Semaphore(concurrency)

        async def fetch(submission_id: int) -> tuple[int, str | None]:
            async with sem:
                try:
                    source = await self.get_submission_source_raw(submission_id)
                    return submission_id, source
                except httpx.HTTPStatusError:
                    return submission_id, None

        pairs = await asyncio.gather(*(fetch(i) for i in ids))
        return {sid: src for sid, src in pairs if src is not None}

    @staticmethod
    def language_to_ext(language: str) -> str:
        return LANGUAGE_EXTENSIONS.get(language, "txt")
```

- [ ] **Step 6: Run all dmoj_client tests**

```bash
pytest tests/test_dmoj_client.py -v
```

Expected output (all pass):
```
tests/test_dmoj_client.py::test_get_contest_participants_returns_usernames PASSED
tests/test_dmoj_client.py::test_get_contest_participants_raises_on_404 PASSED
tests/test_dmoj_client.py::test_get_submissions_paginates PASSED
tests/test_dmoj_client.py::test_get_submission_source_raw_returns_code PASSED
tests/test_dmoj_client.py::test_get_all_sources_returns_dict PASSED
tests/test_dmoj_client.py::test_get_all_sources_omits_failed_submissions PASSED
```

- [ ] **Step 7: Commit**

```bash
git add app/dmoj_client.py tests/test_dmoj_client.py
git commit -m "feat: replace source fetching with /src/{id}/raw and concurrent get_all_sources"
```

---

## Task B: Refactor `/download` handler in `main.py`

> **Agent note:** Task A must be merged/committed before starting this task, since `main.py` depends on the new `get_all_sources` method. Work only in `app/main.py` and `tests/test_download.py`.

**Files:**
- Modify: `app/main.py`
- Modify: `tests/test_download.py`

- [ ] **Step 1: Write failing test for the happy path download**

Add this test to `tests/test_download.py`:

```python
@pytest.mark.asyncio
async def test_download_returns_zip_with_sources():
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
            response = await client.get("/download?slug=ioi2025")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert b"PK" in response.content  # ZIP magic bytes
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_download.py::test_download_returns_zip_with_sources -v
```

Expected: `FAILED` — the current handler calls `/api/v2/submission/1` which isn't mocked, causing an error.

- [ ] **Step 3: Write failing test for index continuity (no gaps)**

Add this test to `tests/test_download.py`:

```python
@pytest.mark.asyncio
async def test_download_index_has_no_gaps_when_source_missing():
    import zipfile, io
    with respx.mock:
        respx.get(f"{BASE}/api/v2/contest/ioi2025").mock(return_value=httpx.Response(200, json={
            "data": {"object": {"key": "ioi2025", "rankings": [{"user": "alice"}]}}
        }))
        respx.get(f"{BASE}/api/v2/submissions").mock(return_value=httpx.Response(200, json={
            "data": {
                "objects": [
                    {"id": 1, "user": "alice", "problem": "prob_a", "result": "AC",
                     "language": "PY3", "date": "2025-05-15T14:30:22+00:00"},
                    {"id": 2, "user": "alice", "problem": "prob_a", "result": "WA",
                     "language": "PY3", "date": "2025-05-15T14:35:00+00:00"},
                    {"id": 3, "user": "alice", "problem": "prob_a", "result": "AC",
                     "language": "PY3", "date": "2025-05-15T14:40:00+00:00"},
                ],
                "has_more": False
            }
        }))
        # Sub 2 returns 403 (no source available)
        respx.get(f"{BASE}/src/1/raw").mock(return_value=httpx.Response(200, text="code1"))
        respx.get(f"{BASE}/src/2/raw").mock(return_value=httpx.Response(403))
        respx.get(f"{BASE}/src/3/raw").mock(return_value=httpx.Response(200, text="code3"))

        async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client:
            await client.post("/login", data={"username": "user1", "password": "pass"})
            response = await client.get("/download?slug=ioi2025")

    assert response.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(response.content))
    names = zf.namelist()
    # Should have index 1 and 2 (not 1 and 3)
    assert any("1_alice" in n for n in names)
    assert any("2_alice" in n for n in names)
    assert not any("3_alice" in n for n in names)
```

- [ ] **Step 4: Run new tests to verify they fail**

```bash
pytest tests/test_download.py::test_download_returns_zip_with_sources tests/test_download.py::test_download_index_has_no_gaps_when_source_missing -v
```

Expected: both `FAILED`.

- [ ] **Step 5: Refactor the `/download` handler in `main.py`**

Replace the `/download` endpoint with this implementation:

```python
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

    return StreamingResponse(
        stream_contest_zip(iter(subs)),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{sanitize_name(slug)}.zip"'},
    )
```

Also remove the unused `ContestNotFoundError` import line — wait, it's still used. Keep all imports as-is. The only import to remove is nothing — `DMOJClient` and `ContestNotFoundError` are both still used.

- [ ] **Step 6: Run all download tests**

```bash
pytest tests/test_download.py -v
```

Expected output (all pass):
```
tests/test_download.py::test_download_unknown_slug_shows_error PASSED
tests/test_download.py::test_download_unauthenticated_redirects PASSED
tests/test_download.py::test_download_returns_zip_with_sources PASSED
tests/test_download.py::test_download_index_has_no_gaps_when_source_missing PASSED
```

- [ ] **Step 7: Run full test suite**

```bash
pytest -v
```

Expected: all tests pass. If any pre-existing tests fail, investigate before committing.

- [ ] **Step 8: Commit**

```bash
git add app/main.py tests/test_download.py
git commit -m "fix: use get_all_sources in download handler, fix index counter gaps"
```

---

## Verification

After both tasks are merged, do a manual end-to-end check:

```bash
# Start server
HTTPS_ONLY=false source .venv/bin/activate && python3 -m uvicorn app.main:app --reload --port 8000

# In another terminal — login and download
curl -sc /tmp/cookies.txt -X POST http://localhost:8000/login \
  -d "username=testuser&password=test123" \
  -H "Content-Type: application/x-www-form-urlencoded" > /dev/null

curl -b /tmp/cookies.txt "http://localhost:8000/download?slug=omipsz26e1" \
  -o /tmp/omipsz26e1.zip -w "\nHTTP: %{http_code} | Size: %{size_download} bytes | Time: %{time_total}s\n"

# Inspect ZIP
python3 -c "import zipfile; z=zipfile.ZipFile('/tmp/omipsz26e1.zip'); print(f'{len(z.namelist())} files'); print('\n'.join(z.namelist()[:10]))"
```

Expected: HTTP 200, ZIP with 729 files (or fewer if any sources fail), completed in under 60 seconds.
