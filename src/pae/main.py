"""FastAPI entry point for Pipeline Auto Extraction."""

from fastapi import FastAPI

from pae import __version__
from pae.config import get_settings


def create_app() -> FastAPI:
    """Build the API application without performing external side effects."""

    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        version=__version__,
        description="Generate validated data-pipeline code from confirmed specifications.",
    )

    @application.get("/health", tags=["operations"])
    def health() -> dict[str, str]:
        """Report process health for local development and deployment probes."""

        return {
            "status": "ok",
            "service": settings.app_name,
            "version": __version__,
            "environment": settings.environment,
        }

    return application


app = create_app()
