"""Versioned authenticated API for project and job persistence."""

from __future__ import annotations

from contextlib import suppress
from dataclasses import asdict
from io import BytesIO
from typing import Annotated, Any, cast

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    Header,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from pydantic import Field

from pae import __version__
from pae.ai.models import AvailableField, RequirementRequest
from pae.ai.service import RequirementInterpreter
from pae.connectors.models import (
    DatabaseCatalog,
    DatabaseConnectionConfig,
    DatabaseSampleRequest,
)
from pae.connectors.service import DatabaseConnectorService
from pae.domain.enums import JobStatus
from pae.domain.models import PipelineSpecification, StrictModel
from pae.exporting import ArtifactExportService
from pae.ingestion.models import IngestionOptions
from pae.ingestion.service import FileIngestionService
from pae.persistence.errors import (
    AuthenticationRequired,
    ConfirmationRequired,
    RevisionConflict,
)
from pae.persistence.models import Permission, Principal, Role
from pae.persistence.repository import Repository
from pae.preview.models import PreviewRequest, PreviewResult
from pae.preview.service import PreviewService
from pae.profiling.models import ProfilingRequest, ProfilingResult, SchemaConfirmation
from pae.profiling.service import SchemaProfiler
from pae.specification import SpecificationConfirmationRequest, build_specification


class ProjectCreate(StrictModel):
    name: str = Field(min_length=1, max_length=120)


class ProjectUpdate(StrictModel):
    name: str = Field(min_length=1, max_length=120)


class MemberUpdate(StrictModel):
    user_id: str = Field(min_length=1)
    role: Role


class SourceConfigCreate(StrictModel):
    kind: str = Field(min_length=1)
    config: dict[str, Any]


class JobCreate(StrictModel):
    operation: str = Field(default="generation", min_length=1)
    model_version: str | None = None
    max_attempts: int = Field(default=3, ge=1, le=5)


class RequirementProposalCreate(StrictModel):
    requirement: str = Field(min_length=1, max_length=4_000)
    language_hint: str = Field(default="auto", pattern=r"^(th|en|mixed|auto)$")


class ExportCreate(StrictModel):
    sample_rows: tuple[dict[str, Any], ...] = Field(default=(), max_length=1_000)
    model_version: str | None = Field(default=None, max_length=200)


def _repository(request: Request) -> Repository:
    return cast(Repository, request.app.state.repository)


def _principal(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> Principal:
    if not authorization or not authorization.startswith("Bearer "):
        raise AuthenticationRequired("A bearer token is required.")
    return _repository(request).authenticate(authorization.removeprefix("Bearer ").strip())


def _ingestion(request: Request) -> FileIngestionService:
    return cast(FileIngestionService, request.app.state.ingestion)


def _database_connectors(request: Request) -> DatabaseConnectorService:
    return cast(DatabaseConnectorService, request.app.state.database_connectors)


def _profiler(request: Request) -> SchemaProfiler:
    return cast(SchemaProfiler, request.app.state.profiler)


def _requirement_interpreter(request: Request) -> RequirementInterpreter:
    return cast(RequirementInterpreter, request.app.state.requirement_interpreter)


def _preview_service(request: Request) -> PreviewService:
    return cast(PreviewService, request.app.state.preview_service)


def _export_service(request: Request) -> ArtifactExportService:
    return cast(ArtifactExportService, request.app.state.export_service)


def _etag(version: int) -> str:
    return f'"{version}"'


def _parse_etag(value: str) -> int:
    try:
        return int(value.strip('"'))
    except ValueError as exc:
        raise RevisionConflict("If-Match must contain the current numeric ETag.") from exc


PrincipalDependency = Annotated[Principal, Depends(_principal)]


async def _execute_export_job(
    repository: Repository,
    export_service: ArtifactExportService,
    principal: Principal,
    project_id: str,
    job_id: str,
    specification: PipelineSpecification,
    body: ExportCreate,
) -> None:
    """Generate and persist a package after returning its trackable job."""

    try:
        repository.report_progress(job_id, 10)
        package = await export_service.build(
            specification,
            sample_rows=body.sample_rows,
            model_version=body.model_version,
        )
        repository.report_progress(job_id, 90)
        completed = repository.complete_job(
            job_id,
            package.manifest,
            package.validation,
            validation_passed=True,
        )
        if completed.status != JobStatus.SUCCEEDED:
            return
        artifact = repository.get_artifact_for_job(principal, project_id, job_id)
        artifact_id = str(artifact["artifact_id"])
        storage_ref = export_service.store(project_id, artifact_id, package.content)
        repository.attach_artifact_package(
            principal,
            project_id,
            artifact_id,
            storage_ref=storage_ref,
            artifact_status=str(package.manifest["artifact_status"]),
            package_checksum=package.checksum,
            manifest=package.manifest,
        )
    except Exception:
        with suppress(Exception):
            repository.fail_job(job_id, "EXPORT_FAILED", retryable=False)


def create_api_router() -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["projects"])

    @router.post("/projects", status_code=status.HTTP_201_CREATED)
    def create_project(
        body: ProjectCreate, request: Request, principal: PrincipalDependency
    ) -> dict[str, Any]:
        project = _repository(request).create_project(principal, body.name)
        return asdict(project)

    @router.get("/projects")
    def list_projects(request: Request, principal: PrincipalDependency) -> list[dict[str, Any]]:
        return [asdict(project) for project in _repository(request).list_projects(principal)]

    @router.get("/projects/{project_id}")
    def get_project(
        project_id: str,
        request: Request,
        response: Response,
        principal: PrincipalDependency,
    ) -> dict[str, Any]:
        project = _repository(request).get_project(principal, project_id)
        response.headers["ETag"] = _etag(project.record_version)
        return asdict(project)

    @router.patch("/projects/{project_id}")
    def update_project(
        project_id: str,
        body: ProjectUpdate,
        request: Request,
        response: Response,
        principal: PrincipalDependency,
        if_match: Annotated[str, Header(alias="If-Match")],
    ) -> dict[str, Any]:
        project = _repository(request).update_project(
            principal, project_id, body.name, _parse_etag(if_match)
        )
        response.headers["ETag"] = _etag(project.record_version)
        return asdict(project)

    @router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_project(
        project_id: str, request: Request, principal: PrincipalDependency
    ) -> Response:
        artifact_refs, sample_refs = _repository(request).delete_project(principal, project_id)
        for storage_ref in artifact_refs:
            _export_service(request).discard(storage_ref)
        for storage_ref in sample_refs:
            _ingestion(request).discard(storage_ref)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
    def logout(request: Request, principal: PrincipalDependency) -> Response:
        _repository(request).deactivate_user(principal)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.put("/projects/{project_id}/members", status_code=status.HTTP_204_NO_CONTENT)
    def update_member(
        project_id: str,
        body: MemberUpdate,
        request: Request,
        principal: PrincipalDependency,
    ) -> Response:
        _repository(request).add_member(principal, project_id, body.user_id, body.role)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.post("/projects/{project_id}/sources", status_code=status.HTTP_201_CREATED)
    def save_source(
        project_id: str,
        body: SourceConfigCreate,
        request: Request,
        principal: PrincipalDependency,
    ) -> dict[str, int]:
        revision = _repository(request).save_source_config(
            principal, project_id, body.kind, body.config
        )
        return {"revision": revision}

    @router.post("/projects/{project_id}/file-sources", status_code=status.HTTP_201_CREATED)
    async def analyze_file_source(
        project_id: str,
        request: Request,
        principal: PrincipalDependency,
        file: Annotated[UploadFile, File()],
        encoding: Annotated[str | None, Form()] = None,
        delimiter: Annotated[str | None, Form()] = None,
        sheet_name: Annotated[str | None, Form()] = None,
        filename_pattern: Annotated[str | None, Form()] = None,
        recursive: Annotated[bool, Form()] = False,
        sample_row_limit: Annotated[int, Form(ge=1, le=100_000)] = 10_000,
    ) -> dict[str, Any]:
        repository = _repository(request)
        repository.get_project(principal, project_id, Permission.EDIT)
        ingestion = _ingestion(request)
        ingestion.cleanup_expired()
        content = await file.read(ingestion.max_file_bytes + 1)
        options = IngestionOptions(
            encoding=encoding,
            delimiter=delimiter,
            sheet_name=sheet_name,
            filename_pattern=filename_pattern,
            recursive=recursive,
            sample_row_limit=sample_row_limit,
        )
        stored = ingestion.ingest(file.filename or "", content, file.content_type, options)
        profile = _profiler(request).profile(
            stored.sample_rows, total_rows=stored.analysis.metadata.total_rows
        )
        if stored.analysis.metadata.truncated:
            profile = profile.model_copy(
                update={
                    "truncated": True,
                    "warnings": (*profile.warnings, "Profile metrics use a bounded row sample."),
                }
            )
        source_config = {
            "file_format": stored.analysis.metadata.file_format,
            "original_name": stored.analysis.metadata.original_name,
            "content_type": stored.analysis.metadata.content_type,
            "size_bytes": stored.analysis.metadata.size_bytes,
            "sha256": stored.analysis.metadata.sha256,
            "encoding": stored.analysis.metadata.encoding,
            "delimiter": stored.analysis.metadata.delimiter,
            "sheet_name": stored.analysis.metadata.sheet_name,
            "runtime": stored.analysis.runtime.model_dump(mode="json"),
            "columns": [
                column.model_dump(mode="json") for column in stored.analysis.metadata.columns
            ],
            "profile": profile.model_dump(mode="json"),
        }
        try:
            revision, sample_id = repository.save_ingested_file(
                principal,
                project_id,
                source_config,
                stored.storage_ref,
                stored.expires_at,
            )
        except Exception:
            ingestion.discard(stored.storage_ref)
            raise
        return {
            "revision": revision,
            "sample_id": sample_id,
            "analysis": stored.analysis.model_dump(mode="json"),
            "profile": profile.model_dump(mode="json"),
            "expires_at": stored.expires_at,
        }

    @router.post(
        "/projects/{project_id}/database-sources/test", status_code=status.HTTP_204_NO_CONTENT
    )
    async def test_database_source(
        project_id: str,
        body: DatabaseConnectionConfig,
        request: Request,
        principal: PrincipalDependency,
    ) -> Response:
        _repository(request).get_project(principal, project_id, Permission.EDIT)
        await _database_connectors(request).test_connection(body)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.post("/projects/{project_id}/database-sources/catalog")
    async def database_source_catalog(
        project_id: str,
        body: DatabaseConnectionConfig,
        request: Request,
        principal: PrincipalDependency,
    ) -> DatabaseCatalog:
        _repository(request).get_project(principal, project_id, Permission.EDIT)
        return await _database_connectors(request).catalog(body)

    @router.post(
        "/projects/{project_id}/database-sources/analyze", status_code=status.HTTP_201_CREATED
    )
    async def analyze_database_source(
        project_id: str,
        body: DatabaseSampleRequest,
        request: Request,
        principal: PrincipalDependency,
    ) -> dict[str, Any]:
        repository = _repository(request)
        repository.get_project(principal, project_id, Permission.EDIT)
        sample = await _database_connectors(request).sample(body)
        profile = _profiler(request).profile(sample.rows)
        if sample.truncated:
            profile = profile.model_copy(
                update={
                    "truncated": True,
                    "warnings": (*profile.warnings, "Profile metrics use a bounded row sample."),
                }
            )
        source_config = {
            "database_type": body.connection.database_type,
            "host": body.connection.host,
            "port": body.connection.port,
            "database": body.connection.database,
            "username": body.connection.username,
            "connection_ref": body.connection.connection_ref,
            "tls_mode": body.connection.tls_mode,
            "schema_name": body.schema_name,
            "object_name": body.object_name,
            "read_only_query": body.read_only_query,
            "sample_limit": min(body.sample_limit, _database_connectors(request).max_sample_rows),
            "columns": list(sample.columns),
            "profile": profile.model_dump(mode="json"),
        }
        revision = repository.save_source_config(principal, project_id, "database", source_config)
        return {
            "revision": revision,
            "sample": sample.model_dump(mode="json"),
            "profile": profile.model_dump(mode="json"),
        }

    @router.post("/projects/{project_id}/profiles")
    def profile_rows(
        project_id: str,
        body: ProfilingRequest,
        request: Request,
        principal: PrincipalDependency,
    ) -> ProfilingResult:
        _repository(request).get_project(principal, project_id, Permission.EDIT)
        limit = min(body.sample_limit, _profiler(request).max_sample_rows)
        return _profiler(request).profile(
            body.rows[:limit], total_rows=body.total_rows or len(body.rows)
        )

    @router.get("/projects/{project_id}/schema")
    def get_project_schema(
        project_id: str, request: Request, principal: PrincipalDependency
    ) -> dict[str, Any]:
        return _repository(request).get_schema(principal, project_id)

    @router.post("/projects/{project_id}/schema/confirm")
    def confirm_project_schema(
        project_id: str,
        body: SchemaConfirmation,
        request: Request,
        principal: PrincipalDependency,
    ) -> dict[str, Any]:
        return _repository(request).confirm_schema(principal, project_id, body)

    @router.post(
        "/projects/{project_id}/requirement-proposals", status_code=status.HTTP_201_CREATED
    )
    async def create_requirement_proposal(
        project_id: str,
        body: RequirementProposalCreate,
        request: Request,
        principal: PrincipalDependency,
    ) -> dict[str, Any]:
        repository = _repository(request)
        schema = repository.get_confirmed_schema(principal, project_id, Permission.EDIT)
        ai_request = RequirementRequest(
            requirement=body.requirement,
            available_fields=tuple(
                AvailableField(name=field.name, data_type=field.confirmed_type)
                for field in schema.fields
                if field.selected
            ),
            language_hint=body.language_hint,  # type: ignore[arg-type]
        )
        result = await _requirement_interpreter(request).analyze(ai_request)
        proposal_id = repository.save_requirement_proposal(
            principal,
            project_id,
            ai_request.model_dump(mode="json"),
            result.analysis.model_dump(mode="json"),
            result.model,
        )
        return {
            "proposal_id": proposal_id,
            "revision": schema.revision,
            "analysis": result.analysis.model_dump(mode="json"),
            "model": result.model,
            "metrics": asdict(result.metrics),
            "requires_confirmation": True,
        }

    @router.get("/projects/{project_id}/requirement-proposals/{proposal_id}")
    def get_requirement_proposal(
        project_id: str,
        proposal_id: str,
        request: Request,
        principal: PrincipalDependency,
    ) -> dict[str, Any]:
        return _repository(request).get_requirement_proposal(principal, project_id, proposal_id)

    @router.post("/projects/{project_id}/specification/confirm-from-proposal")
    def confirm_specification_from_proposal(
        project_id: str,
        body: SpecificationConfirmationRequest,
        request: Request,
        principal: PrincipalDependency,
    ) -> dict[str, Any]:
        repository = _repository(request)
        proposal = repository.get_requirement_proposal(principal, project_id, body.proposal_id)
        analysis = proposal["analysis"]
        if analysis.get("status") != "ready":
            raise ConfirmationRequired(
                "Only a ready, schema-validated proposal can be confirmed. "
                "Resolve clarification questions first."
            )
        if (analysis.get("assumptions") or analysis.get("warnings")) and not (
            body.assumptions_acknowledged
        ):
            raise ConfirmationRequired(
                "Review and acknowledge proposal assumptions and warnings before confirmation."
            )
        schema = repository.get_confirmed_schema(principal, project_id, Permission.EDIT)
        source = repository.get_latest_source_config(principal, project_id)
        specification = build_specification(project_id, source, schema, body, principal.user_id)
        fingerprint = repository.confirm_specification(principal, project_id, specification)
        return {
            "revision": specification.revision,
            "specification_id": str(specification.specification_id),
            "specification_fingerprint": fingerprint,
            "confirmed": True,
        }

    @router.post("/projects/{project_id}/specification/confirm")
    def confirm_specification(
        project_id: str,
        body: PipelineSpecification,
        request: Request,
        principal: PrincipalDependency,
    ) -> dict[str, Any]:
        fingerprint = _repository(request).confirm_specification(principal, project_id, body)
        return {"revision": body.revision, "specification_fingerprint": fingerprint}

    @router.get("/projects/{project_id}/specification/versions")
    def specification_versions(
        project_id: str, request: Request, principal: PrincipalDependency
    ) -> list[dict[str, Any]]:
        versions = _repository(request).list_specification_versions(principal, project_id)
        return [version.model_dump(mode="json") for version in versions]

    @router.post("/projects/{project_id}/preview")
    async def preview_specification(
        project_id: str,
        body: PreviewRequest,
        request: Request,
        principal: PrincipalDependency,
    ) -> PreviewResult:
        repository = _repository(request)
        specification = repository.get_current_specification(principal, project_id, Permission.EDIT)
        return await _preview_service(request).preview(
            specification, body.rows, timeout_seconds=body.timeout_seconds
        )

    @router.post("/projects/{project_id}/generation-jobs", status_code=status.HTTP_202_ACCEPTED)
    def submit_generation_job(
        project_id: str,
        body: JobCreate,
        request: Request,
        response: Response,
        principal: PrincipalDependency,
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1)],
    ) -> dict[str, Any]:
        job, created = _repository(request).submit_job(
            principal,
            project_id,
            body.operation,
            idempotency_key,
            generator_version=__version__,
            model_version=body.model_version,
            max_attempts=body.max_attempts,
        )
        response.status_code = status.HTTP_202_ACCEPTED if created else status.HTTP_200_OK
        return asdict(job)

    @router.get("/projects/{project_id}/jobs/{job_id}")
    def get_job(
        project_id: str,
        job_id: str,
        request: Request,
        principal: PrincipalDependency,
    ) -> dict[str, Any]:
        return asdict(_repository(request).get_job(principal, project_id, job_id))

    @router.post("/projects/{project_id}/jobs/{job_id}/cancel")
    def cancel_job(
        project_id: str,
        job_id: str,
        request: Request,
        principal: PrincipalDependency,
    ) -> dict[str, Any]:
        return asdict(_repository(request).cancel_job(principal, project_id, job_id))

    @router.get("/projects/{project_id}/jobs/{job_id}/validation")
    def get_job_validation(
        project_id: str,
        job_id: str,
        request: Request,
        principal: PrincipalDependency,
    ) -> dict[str, Any]:
        return _repository(request).get_job_validation(principal, project_id, job_id)

    @router.get("/projects/{project_id}/artifacts/{artifact_id}")
    def get_artifact(
        project_id: str,
        artifact_id: str,
        request: Request,
        principal: PrincipalDependency,
    ) -> dict[str, Any]:
        return _repository(request).get_artifact_manifest(principal, project_id, artifact_id)

    @router.get("/projects/{project_id}/artifacts")
    def list_artifacts(
        project_id: str, request: Request, principal: PrincipalDependency
    ) -> tuple[dict[str, Any], ...]:
        return _repository(request).list_artifacts(principal, project_id)

    @router.post("/projects/{project_id}/exports", status_code=status.HTTP_202_ACCEPTED)
    async def create_export(
        project_id: str,
        body: ExportCreate,
        background_tasks: BackgroundTasks,
        request: Request,
        response: Response,
        principal: PrincipalDependency,
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1)],
    ) -> dict[str, Any]:
        repository = _repository(request)
        job, created = repository.submit_job(
            principal,
            project_id,
            "export-package",
            idempotency_key,
            generator_version=__version__,
            model_version=body.model_version,
        )
        if not created and job.status == "succeeded":
            response.status_code = status.HTTP_200_OK
            return repository.get_artifact_for_job(principal, project_id, job.job_id)
        if not created:
            response.status_code = status.HTTP_202_ACCEPTED
            return asdict(job)
        claimed = repository.claim_job(job.job_id, f"api:{request.state.request_id}")
        specification = repository.get_current_specification(principal, project_id, Permission.EDIT)
        background_tasks.add_task(
            _execute_export_job,
            repository,
            _export_service(request),
            principal,
            project_id,
            job.job_id,
            specification,
            body,
        )
        response.status_code = status.HTTP_202_ACCEPTED
        return asdict(claimed)

    @router.get("/projects/{project_id}/artifacts/{artifact_id}/download", response_model=None)
    def authorize_artifact_download(
        project_id: str,
        artifact_id: str,
        request: Request,
        principal: PrincipalDependency,
    ) -> Response | dict[str, Any]:
        """Authorize and stream a stored immutable package."""

        repository = _repository(request)
        manifest = repository.authorize_artifact_download(principal, project_id, artifact_id)
        if not manifest["download_available"]:
            return manifest
        content = _export_service(request).read(
            repository.get_artifact_storage_ref(principal, project_id, artifact_id)
        )
        return StreamingResponse(
            BytesIO(content),
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="pae-{artifact_id}.zip"',
                "X-Content-SHA256": str(manifest["package_checksum"]),
                "X-PAE-Artifact-Status": str(manifest["artifact_status"]),
            },
        )

    @router.get("/projects/{project_id}/audit-events")
    def audit_events(
        project_id: str, request: Request, principal: PrincipalDependency
    ) -> list[dict[str, Any]]:
        return list(_repository(request).list_audit_events(principal, project_id))

    return router
