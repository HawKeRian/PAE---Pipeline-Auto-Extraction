"""FastAPI entry point for Pipeline Auto Extraction."""

import asyncio
import logging
import time
from collections import defaultdict, deque
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from uuid import uuid4

import httpx
import psutil
from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import RequestResponseEndpoint

from pae import __version__
from pae.ai.fallback import ClarificationFallbackProvider
from pae.ai.ollama import OllamaProvider
from pae.ai.service import RequirementInterpreter
from pae.api import create_api_router
from pae.config import Settings, get_settings
from pae.connectors.drivers import DefaultDatabaseDriverFactory
from pae.connectors.network import DatabaseNetworkPolicy
from pae.connectors.secrets import EnvironmentSecretResolver
from pae.connectors.service import DatabaseConnectorService
from pae.exporting import ArtifactExportService
from pae.ingestion import FileIngestionService
from pae.observability import AlertDispatcher, MetricsRegistry, configure_json_logging
from pae.persistence.database import Database
from pae.persistence.errors import ApplicationError, RateLimitExceeded
from pae.persistence.repository import Repository
from pae.preview.service import PreviewService
from pae.production_ui import create_production_ui_router
from pae.profiling.service import SchemaProfiler
from pae.sandbox import SandboxRunner


async def _retention_cleanup_loop(ingestion: FileIngestionService, interval_seconds: int) -> None:
    while True:
        await asyncio.sleep(interval_seconds)
        ingestion.cleanup_expired()


def create_app(
    settings: Settings | None = None,
    repository: Repository | None = None,
    alert_client: httpx.AsyncClient | None = None,
) -> FastAPI:
    """Build the API application and initialize local persistence."""

    settings = settings or get_settings()
    if settings.structured_logging:
        configure_json_logging(settings.log_level)
    if repository is None:
        database = Database(settings.resolved_database_path)
        database.migrate()
        repository = Repository(database, queue_capacity=settings.queue_capacity)
    if settings.bootstrap_token is not None:
        repository.create_user(
            settings.bootstrap_user_id,
            settings.bootstrap_user_name,
            settings.bootstrap_token.get_secret_value(),
        )
    ingestion = FileIngestionService(
        settings.sample_storage_path,
        max_file_bytes=settings.max_upload_bytes,
        max_sample_rows=settings.max_sample_rows,
        max_columns=settings.max_sample_columns,
        retention_hours=settings.sample_retention_hours,
    )
    database_connectors = DatabaseConnectorService(
        DefaultDatabaseDriverFactory(query_timeout_seconds=settings.database_query_timeout_seconds),
        EnvironmentSecretResolver(),
        DatabaseNetworkPolicy(
            settings.database_host_allowlist,
            allow_private_hosts=settings.database_allow_private_hosts,
        ),
        max_sample_rows=settings.database_sample_rows,
        default_timeout_seconds=settings.database_query_timeout_seconds,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        ingestion.cleanup_expired()
        interval = max(60, min(3_600, settings.sample_retention_hours * 1_800))
        cleanup_task = asyncio.create_task(_retention_cleanup_loop(ingestion, interval))
        try:
            yield
        finally:
            cleanup_task.cancel()
            with suppress(asyncio.CancelledError):
                await cleanup_task

    application = FastAPI(
        title=settings.app_name,
        version=__version__,
        description="Generate validated data-pipeline code from confirmed specifications.",
        lifespan=lifespan,
    )
    application.state.repository = repository
    application.state.settings = settings
    application.state.ingestion = ingestion
    application.state.database_connectors = database_connectors
    application.state.profiler = SchemaProfiler(max_sample_rows=settings.max_sample_rows)
    sandbox = SandboxRunner(
        settings.sandbox_workspace_path,
        timeout_seconds=settings.sandbox_timeout_seconds,
        memory_limit_bytes=settings.sandbox_memory_mb * 1024 * 1024,
        cpu_limit_seconds=settings.sandbox_cpu_seconds,
        output_limit_bytes=settings.sandbox_output_mb * 1024 * 1024,
    )
    application.state.preview_service = PreviewService(sandbox)
    application.state.export_service = ArtifactExportService(settings.generated_dir, sandbox)
    application.state.requirement_interpreter = RequirementInterpreter(
        OllamaProvider(
            base_url=settings.ollama_base_url,
            model=settings.ai_model,
            timeout_seconds=settings.ai_timeout_seconds,
        ),
        ClarificationFallbackProvider(),
    )

    rate_windows: dict[str, deque[float]] = defaultdict(deque)
    metrics = MetricsRegistry()
    application.state.metrics = metrics
    request_logger = logging.getLogger("pae.requests")
    alert_dispatcher = AlertDispatcher(
        settings.alert_webhook_url.get_secret_value() if settings.alert_webhook_url else None,
        timeout_seconds=settings.alert_webhook_timeout_seconds,
        cooldown_seconds=settings.alert_webhook_cooldown_seconds,
        client=alert_client,
    )
    application.state.alert_dispatcher = alert_dispatcher

    @application.middleware("http")
    async def request_identity(request: Request, call_next: RequestResponseEndpoint) -> Response:
        started = time.perf_counter()
        request.state.request_id = request.headers.get("X-Request-ID", str(uuid4()))
        if request.url.path.startswith("/api/"):
            now = time.monotonic()
            host = request.client.host if request.client else "local"
            key = f"{host}:{request.url.path}"
            window = rate_windows[key]
            cutoff = now - settings.rate_limit_window_seconds
            while window and window[0] <= cutoff:
                window.popleft()
            if len(window) >= settings.rate_limit_requests:
                exc = RateLimitExceeded("Too many requests. Retry after the rate-limit window.")
                return JSONResponse(
                    status_code=exc.status_code,
                    content={
                        "error": {
                            "code": exc.code,
                            "message": exc.message,
                            "details": exc.details,
                            "request_id": request.state.request_id,
                            "retryable": exc.retryable,
                        }
                    },
                    headers={
                        "X-Request-ID": request.state.request_id,
                        "Retry-After": str(settings.rate_limit_window_seconds),
                        "Cache-Control": "no-store",
                        "X-Content-Type-Options": "nosniff",
                    },
                )
            window.append(now)
        response = await call_next(request)
        duration = time.perf_counter() - started
        route_object = request.scope.get("route")
        route = str(getattr(route_object, "path", request.url.path))
        metrics.observe(request.method, route, response.status_code, duration)
        if settings.structured_logging:
            request_logger.info(
                "request.completed",
                extra={
                    "request_id": request.state.request_id,
                    "method": request.method,
                    "route": route,
                    "status_code": response.status_code,
                    "duration_ms": round(duration * 1_000, 3),
                },
            )
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'"
        )
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        if settings.environment == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    @application.exception_handler(ApplicationError)
    async def application_error(request: Request, exc: ApplicationError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                    "request_id": request.state.request_id,
                    "retryable": exc.retryable,
                }
            },
        )

    @application.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {"location": list(error["loc"]), "message": error["msg"], "type": error["type"]}
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "REQUEST_VALIDATION_FAILED",
                    "message": "The request did not match the API contract.",
                    "details": {"errors": details},
                    "request_id": request.state.request_id,
                    "retryable": False,
                }
            },
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

    @application.get("/ready", tags=["operations"])
    async def readiness() -> JSONResponse:
        """Report dependency readiness and actionable local alerts."""

        components: dict[str, dict[str, str]] = {}
        ready = True
        try:
            queue = repository.operational_status()
            components["persistence"] = {"status": "ok"}
        except Exception:
            queue = {"queued": 0, "running": 0, "failed": 0}
            components["persistence"] = {"status": "unavailable"}
            ready = False
        try:
            settings.generated_dir.mkdir(parents=True, exist_ok=True)
            components["artifact_storage"] = {"status": "ok"}
        except OSError:
            components["artifact_storage"] = {"status": "unavailable"}
            ready = False
        if settings.readiness_require_model:
            try:
                async with httpx.AsyncClient(
                    timeout=settings.readiness_model_timeout_seconds
                ) as client:
                    model_response = await client.get(
                        f"{settings.ollama_base_url.rstrip('/')}/api/tags"
                    )
                    model_response.raise_for_status()
                    model_names = {
                        str(item.get("name", "")).split(":latest", 1)[0]
                        for item in model_response.json().get("models", [])
                    }
                model_ready = settings.ai_model in model_names
                components["local_model"] = {"status": "ok" if model_ready else "model_missing"}
                ready = ready and model_ready
            except (httpx.HTTPError, ValueError, TypeError):
                components["local_model"] = {"status": "unavailable"}
                ready = False
        else:
            components["local_model"] = {"status": "optional_not_checked"}
        alerts = []
        if queue["queued"] >= settings.alert_queue_depth:
            alerts.append("job_queue_depth_high")
        if alerts:
            request_logger.warning("operational.alert", extra={"route": "/ready"})
        alert_delivery = await alert_dispatcher.deliver(
            alerts,
            {
                "environment": settings.environment,
                "queue": queue,
                "service": settings.app_name,
            },
        )
        if alerts:
            metrics.record_alert_delivery(alert_delivery)
        payload = {
            "status": "ready" if ready else "not_ready",
            "components": components,
            "queue": queue,
            "alerts": alerts,
            "alert_delivery": alert_delivery,
        }
        return JSONResponse(payload, status_code=200 if ready else 503)

    @application.get("/metrics", response_class=PlainTextResponse, tags=["operations"])
    def prometheus_metrics() -> str:
        queue = repository.operational_status()
        return metrics.render(
            queue_depth=queue["queued"],
            process_rss_bytes=psutil.Process().memory_info().rss,
        )

    package_directory = Path(__file__).resolve().parent
    application.mount(
        "/static",
        StaticFiles(directory=package_directory / "static"),
        name="static",
    )
    application.include_router(create_production_ui_router(settings))

    application.include_router(create_api_router())

    return application


app = create_app()
