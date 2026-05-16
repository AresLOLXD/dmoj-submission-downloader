# Bug Fixes: Source Fetching & Download Performance

**Date:** 2026-05-16
**Status:** Approved

## Context

During testing with real contests on `dmoj.olimpiadadeinformatica.org.mx`, three bugs were identified:

1. **`KeyError: 'source'`** — The DMOJ API v2 (`/api/v2/submission/{id}`) never returns a `source` field on this instance, for any language (Karel, C++, etc.). The original code assumed it always would.
2. **Index counter desync** — The submission index counter increments before knowing whether source is available. If a submission is skipped, indices have gaps (1, 3, 5…), making the ZIP confusing.
3. **Sequential HTTP bottleneck** — The download loop makes one HTTP request per submission sequentially. For a 729-submission contest this takes several minutes.

## Solution

### Bug 1 & 2 — Source fetching via `/src/{id}/raw`

Replace `get_submission_source` (which called `/api/v2/submission/{id}`) with a new method `get_submission_source_raw` that calls `/src/{id}/raw`. This endpoint:
- Works for all languages (Karel, C++, Java, etc.)
- Is authenticated with the same Bearer token
- Returns plain text source code

The index counter moves to the moment the submission is appended to `subs`, after confirming a source exists. This eliminates gaps.

### Bug 3 — Concurrent source fetching

Add `get_all_sources(ids: list[int], concurrency: int = 20) -> dict[int, str]` to `DMOJClient`. It fetches all sources in parallel using `asyncio.Semaphore(20)` + `asyncio.gather`, capping simultaneous requests to avoid overwhelming the DMOJ server. Expected improvement: ~2-4 minutes → ~10-20 seconds for 700+ submissions.

In `main.py`, the download handler:
1. Collects all submission metadata first (already fast — paginated list endpoint).
2. Calls `get_all_sources` once with all IDs.
3. Builds `subs` list, incrementing counter only for submissions with a source present.
4. If a source fetch fails (HTTP error), that submission is silently omitted.

## Files Changed

| File | Change |
|------|--------|
| `app/dmoj_client.py` | Remove `get_submission_source`; add `get_submission_source_raw` and `get_all_sources` |
| `app/main.py` | Refactor download handler to use `get_all_sources`; fix counter placement |

No changes to `zip_builder.py`, `auth.py`, `admin.py`, `models.py`, or templates.

## Implementation Tasks (for parallel agents)

These two tasks are independent and can be worked in parallel:

**Task A — `dmoj_client.py`**
- Remove `get_submission_source`
- Add `get_submission_source_raw(submission_id: int) -> str` using `/src/{id}/raw`
- Add `get_all_sources(ids: list[int], concurrency: int = 20) -> dict[int, str]` using `asyncio.Semaphore` + `asyncio.gather`

**Task B — `main.py`**
- Refactor `/download` handler: collect metadata first, then call `get_all_sources`, then build `subs` with counter increment after append
- Remove the now-unused `if source is None: continue` guard (or replace with a lookup miss check from the dict)

Both tasks can be verified independently before integration.

## Success Criteria

- `GET /download?slug=omipsz26e1` returns a non-empty ZIP with Karel source files (`.java` extension from `RKL23` or `RKL23` mapped to appropriate ext)
- `GET /download?slug=omijal26prelenguaje` returns a ZIP with C++ source files
- No index gaps in filenames within a user/problem folder
- Download of 700+ submission contest completes in under 60 seconds
