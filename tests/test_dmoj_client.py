import pytest
import respx
import httpx
from app.dmoj_client import DMOJClient, ContestNotFoundError

BASE = "https://dmoj.test"
TOKEN = "test_token"

@pytest.fixture
def make_client():
    return lambda: DMOJClient(base_url=BASE, token=TOKEN)

@pytest.mark.asyncio
async def test_get_contest_participants_returns_usernames(make_client):
    with respx.mock:
        respx.get(f"{BASE}/api/v2/contest/ioi2025").mock(return_value=httpx.Response(200, json={
            "data": {
                "object": {
                    "key": "ioi2025",
                    "rankings": [{"user": "alice"}, {"user": "bob"}]
                }
            }
        }))
        async with make_client() as client:
            participants = await client.get_contest_participants("ioi2025")
    assert participants == ["alice", "bob"]

@pytest.mark.asyncio
async def test_get_contest_participants_raises_on_404(make_client):
    with respx.mock:
        respx.get(f"{BASE}/api/v2/contest/nope").mock(return_value=httpx.Response(404))
        with pytest.raises(ContestNotFoundError):
            async with make_client() as client:
                await client.get_contest_participants("nope")

@pytest.mark.asyncio
async def test_get_submissions_paginates(make_client):
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
        async with make_client() as client:
            submissions = await client.get_contest_submissions("ioi2025")
    assert len(submissions) == 2
    assert submissions[0]["id"] == 1
    assert submissions[1]["id"] == 2

@pytest.mark.asyncio
async def test_get_submission_source_raw_returns_code(make_client):
    with respx.mock:
        respx.get(f"{BASE}/src/42/raw").mock(
            return_value=httpx.Response(200, text="print('hello')")
        )
        async with make_client() as client:
            source = await client.get_submission_source_raw(42)
    assert source == "print('hello')"


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
