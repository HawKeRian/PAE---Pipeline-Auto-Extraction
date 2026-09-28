"""Production web interface shell backed exclusively by versioned APIs."""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from pae.config import Settings


def create_production_ui_router(settings: Settings) -> APIRouter:
    """Serve the API-backed interface; no mock routes are registered."""

    router = APIRouter(include_in_schema=False)
    templates = Jinja2Templates(directory=Path(__file__).resolve().parent / "templates")

    @router.get("/ui", response_class=HTMLResponse)
    def production_ui(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request=request,
            name="production_ui.html",
            context={"app_name": settings.app_name, "environment": settings.environment},
        )

    return router
