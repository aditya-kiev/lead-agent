import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_cors_preflight_returns_wildcard(client):
    r = await client.options(
        "/health",
        headers={"origin": "http://localhost:5500", "access-control-request-method": "GET"},
    )
    assert r.headers.get("access-control-allow-origin") == "*"


@pytest.mark.asyncio
async def test_cors_get_returns_wildcard(client):
    r = await client.get("/health", headers={"origin": "http://localhost:5500"})
    assert r.headers.get("access-control-allow-origin") == "*"


@pytest.mark.asyncio
async def test_cors_null_origin_accepted(client):
    r = await client.options(
        "/health",
        headers={"origin": "null", "access-control-request-method": "GET"},
    )
    assert r.headers.get("access-control-allow-origin") == "*"


@pytest.mark.asyncio
async def test_cors_file_origin_accepted(client):
    r = await client.options(
        "/health",
        headers={"origin": "file://", "access-control-request-method": "GET"},
    )
    assert r.headers.get("access-control-allow-origin") == "*"
