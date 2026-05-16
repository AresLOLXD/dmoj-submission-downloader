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
