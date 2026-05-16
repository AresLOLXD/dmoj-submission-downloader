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
