"""Smoke tests for the application foundation."""

import pytest
from httpx import ASGITransport, AsyncClient

from pae.main import app


@pytest.fixture
def anyio_backend() -> str:
    """Use the asyncio backend provided by the runtime dependencies."""

    return "asyncio"


@pytest.mark.anyio
async def test_health_returns_service_metadata() -> None:
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "Pipeline Auto Extraction",
        "version": "0.1.0",
        "environment": "development",
    }
