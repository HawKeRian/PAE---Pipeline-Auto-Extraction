"""Smoke and security tests for the production API-backed UI."""

import pytest
from httpx import ASGITransport, AsyncClient

from pae.config import Settings
from pae.main import create_app


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_production_ui_exposes_complete_real_workflow() -> None:
    application = create_app(Settings(environment="testing", enable_mock_ui=True))
    transport = ASGITransport(app=application)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/ui")

    assert response.status_code == 200
    assert "REAL API WORKFLOW" in response.text
    assert response.text.count('class="card step-panel"') == 6
    assert "Local Llama" not in response.text  # UI text is uppercase and never claims a stub.
    assert "LOCAL LLAMA" in response.text
    assert "ระบบ profile และ suggest columns ก่อนให้คุณเลือก" in response.text
    assert "/static/production_ui.js" in response.text
    assert "/ui/mock-export" not in response.text
    assert 'id="create-export"' in response.text
    assert 'id="retry-export"' in response.text
    assert response.headers["x-frame-options"] == "DENY"


@pytest.mark.anyio
async def test_production_ui_is_available_and_mock_is_disabled_in_production() -> None:
    application = create_app(Settings(environment="production", enable_mock_ui=True))
    transport = ASGITransport(app=application)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        ui_response = await client.get("/ui")
        static_response = await client.get("/static/production_ui.css")
        mock_response = await client.get("/ui/mock-export")

    assert ui_response.status_code == 200
    assert static_response.status_code == 200
    assert mock_response.status_code == 404
    assert ui_response.headers["strict-transport-security"].startswith("max-age=")


@pytest.mark.anyio
async def test_ui_javascript_calls_real_versioned_apis_and_uses_session_storage() -> None:
    application = create_app(Settings(environment="testing", enable_mock_ui=True))
    transport = ASGITransport(app=application)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/static/production_ui.js")

    assert response.status_code == 200
    assert "/file-sources" in response.text
    assert "/select-sheet" in response.text
    assert "sheet_selection_required" in response.text
    assert "workbook-sheet" in response.text
    assert "/schema/confirm" in response.text
    assert "/requirement-proposals" in response.text
    assert "/preview" in response.text
    assert "/exports" in response.text
    assert "sessionStorage" in response.text
    assert "localStorage" not in response.text
    assert "mock" not in response.text.lower()
