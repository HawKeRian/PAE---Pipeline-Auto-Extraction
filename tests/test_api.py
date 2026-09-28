"""Authenticated API integration tests and public error-envelope checks."""

import json
import subprocess
import sys
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import UUID, uuid4
from zipfile import ZipFile

from fastapi.testclient import TestClient

from pae.ai.models import RequirementAnalysis, TransformationDraft, ValidationDraft
from pae.ai.provider import AIProviderResult, InferenceMetrics
from pae.ai.service import RequirementInterpreter
from pae.config import Settings
from pae.connectors.models import DatabaseCatalog, DatabaseObject, DatabaseSample
from pae.connectors.service import DatabaseConnectorService
from pae.domain.enums import DataType, OutputFormat, TargetLanguage
from pae.domain.models import (
    FieldDefinition,
    FileDiscoveryContract,
    FileSource,
    OutputContract,
    PipelineSpecification,
    TargetRuntime,
)
from pae.jobs import JobExecutionResult, JobWorker
from pae.main import create_app
from pae.persistence.database import Database
from pae.persistence.models import Role
from pae.persistence.repository import Repository

OWNER_TOKEN = "api-owner-token-with-32-characters"
VIEWER_TOKEN = "api-viewer-token-with-32-characters"
OTHER_TOKEN = "api-other-token-with-32-characters-"


def client_and_repository(tmp_path: Path) -> tuple[TestClient, Repository]:
    database = Database(tmp_path / "api.sqlite3")
    database.migrate()
    repository = Repository(database)
    repository.create_user("api-owner", "API Owner", OWNER_TOKEN)
    repository.create_user("api-viewer", "API Viewer", VIEWER_TOKEN)
    repository.create_user("api-other", "API Other", OTHER_TOKEN)
    settings = Settings(
        environment="testing",
        enable_mock_ui=False,
        data_dir=tmp_path / "data",
        generated_dir=tmp_path / "generated",
        database_path=tmp_path / "unused.sqlite3",
    )
    return TestClient(create_app(settings, repository)), repository


def authorization(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def api_specification(project_id: str, revision: int) -> PipelineSpecification:
    return PipelineSpecification(
        specification_id=uuid4(),
        project_id=UUID(project_id),
        revision=revision,
        name="api-pipeline",
        source_fingerprint="a" * 64,
        sources=(
            FileSource(
                source_id="input",
                file_format="csv",
                original_name="sample.csv",
                runtime=FileDiscoveryContract(filename_pattern="*.csv"),
            ),
        ),
        fields=(
            FieldDefinition(
                source_id="input",
                source_name="amount",
                target_name="amount",
                inferred_type=DataType.DECIMAL,
                confirmed_type=DataType.DECIMAL,
                nullable=False,
                confidence=1,
                null_percentage=0,
            ),
        ),
        output=OutputContract(format=OutputFormat.CSV),
        target=TargetRuntime(language=TargetLanguage.PYTHON),
        confirmed_by="api-owner",
        confirmed_at=datetime.now(UTC),
    )


def test_project_api_crud_etag_and_error_envelope(tmp_path: Path) -> None:
    client, _ = client_and_repository(tmp_path)
    unauthenticated = client.get("/api/v1/projects")
    assert unauthenticated.status_code == 401
    assert unauthenticated.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
    assert "X-Request-ID" in unauthenticated.headers

    created = client.post(
        "/api/v1/projects", json={"name": "API Project"}, headers=authorization(OWNER_TOKEN)
    )
    assert created.status_code == 201
    project_id = created.json()["project_id"]

    opened = client.get(f"/api/v1/projects/{project_id}", headers=authorization(OWNER_TOKEN))
    assert opened.status_code == 200
    assert opened.headers["etag"] == '"1"'

    updated = client.patch(
        f"/api/v1/projects/{project_id}",
        json={"name": "Renamed API Project"},
        headers={**authorization(OWNER_TOKEN), "If-Match": opened.headers["etag"]},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Renamed API Project"

    stale = client.patch(
        f"/api/v1/projects/{project_id}",
        json={"name": "Stale"},
        headers={**authorization(OWNER_TOKEN), "If-Match": '"1"'},
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "REVISION_CONFLICT"

    deleted = client.delete(f"/api/v1/projects/{project_id}", headers=authorization(OWNER_TOKEN))
    assert deleted.status_code == 204


def test_cross_user_and_viewer_cannot_mutate_project(tmp_path: Path) -> None:
    client, repository = client_and_repository(tmp_path)
    created = client.post(
        "/api/v1/projects", json={"name": "Private"}, headers=authorization(OWNER_TOKEN)
    ).json()
    project_id = created["project_id"]

    hidden = client.get(f"/api/v1/projects/{project_id}", headers=authorization(OTHER_TOKEN))
    assert hidden.status_code == 404

    owner = repository.authenticate(OWNER_TOKEN)
    repository.add_member(owner, project_id, "api-viewer", Role.VIEWER)
    visible = client.get(f"/api/v1/projects/{project_id}", headers=authorization(VIEWER_TOKEN))
    assert visible.status_code == 200
    forbidden = client.patch(
        f"/api/v1/projects/{project_id}",
        json={"name": "Not allowed"},
        headers={**authorization(VIEWER_TOKEN), "If-Match": visible.headers["etag"]},
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "PERMISSION_DENIED"


def test_api_validation_and_secret_rejection_are_sanitized(tmp_path: Path) -> None:
    client, _ = client_and_repository(tmp_path)
    invalid = client.post("/api/v1/projects", json={"name": ""}, headers=authorization(OWNER_TOKEN))
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "REQUEST_VALIDATION_FAILED"
    assert "input" not in str(invalid.json()).lower()

    project_id = client.post(
        "/api/v1/projects", json={"name": "Secure"}, headers=authorization(OWNER_TOKEN)
    ).json()["project_id"]
    rejected = client.post(
        f"/api/v1/projects/{project_id}/sources",
        json={"kind": "database", "config": {"password": "do-not-return-this"}},
        headers=authorization(OWNER_TOKEN),
    )
    assert rejected.status_code == 422
    assert rejected.json()["error"]["code"] == "SECRET_VALUE_REJECTED"
    assert "do-not-return-this" not in rejected.text


def test_api_project_specification_job_and_artifact_lifecycle(tmp_path: Path) -> None:
    client, repository = client_and_repository(tmp_path)
    headers = authorization(OWNER_TOKEN)
    project_id = client.post(
        "/api/v1/projects", json={"name": "Lifecycle"}, headers=headers
    ).json()["project_id"]
    assert client.get("/api/v1/projects", headers=headers).json()[0]["project_id"] == project_id

    member = client.put(
        f"/api/v1/projects/{project_id}/members",
        json={"user_id": "api-viewer", "role": "viewer"},
        headers=headers,
    )
    assert member.status_code == 204
    source = client.post(
        f"/api/v1/projects/{project_id}/sources",
        json={
            "kind": "file",
            "config": {"connection_ref": "local://incoming", "filename_pattern": "*.csv"},
        },
        headers=headers,
    )
    assert source.json() == {"revision": 1}

    spec = api_specification(project_id, 1)
    confirmed = client.post(
        f"/api/v1/projects/{project_id}/specification/confirm",
        json=spec.model_dump(mode="json"),
        headers=headers,
    )
    assert confirmed.status_code == 200
    versions = client.get(f"/api/v1/projects/{project_id}/specification/versions", headers=headers)
    assert versions.json()[0]["revision"] == 1

    job_headers = {**headers, "Idempotency-Key": "api-generation"}
    submitted = client.post(
        f"/api/v1/projects/{project_id}/generation-jobs",
        json={"operation": "generation"},
        headers=job_headers,
    )
    assert submitted.status_code == 202
    job_id = submitted.json()["job_id"]
    duplicate = client.post(
        f"/api/v1/projects/{project_id}/generation-jobs",
        json={"operation": "generation"},
        headers=job_headers,
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["job_id"] == job_id
    assert (
        client.get(f"/api/v1/projects/{project_id}/jobs/{job_id}", headers=headers).status_code
        == 200
    )

    worker = JobWorker(repository, worker_id="api-worker")
    completed = worker.run_once(
        lambda _: JobExecutionResult(
            result={"files": ["pipeline.py"]},
            validation_result={"syntax": "passed"},
            validation_passed=True,
        )
    )
    assert completed is not None and completed.status == "succeeded"
    validation = client.get(
        f"/api/v1/projects/{project_id}/jobs/{job_id}/validation", headers=headers
    )
    assert validation.json()["passed"] is True
    with repository.database.connect() as connection:
        artifact_id = str(connection.execute("SELECT artifact_id FROM artifacts").fetchone()[0])
    artifact_url = f"/api/v1/projects/{project_id}/artifacts/{artifact_id}"
    assert client.get(artifact_url, headers=headers).json()["revision"] == 1
    assert client.get(f"{artifact_url}/download", headers=headers).status_code == 200
    cancellable = client.post(
        f"/api/v1/projects/{project_id}/generation-jobs",
        json={"operation": "preview"},
        headers={**headers, "Idempotency-Key": "api-cancel"},
    ).json()
    cancelled = client.post(
        f"/api/v1/projects/{project_id}/jobs/{cancellable['job_id']}/cancel", headers=headers
    )
    assert cancelled.json()["status"] == "cancelled"
    actions = {
        event["action"]
        for event in client.get(
            f"/api/v1/projects/{project_id}/audit-events", headers=headers
        ).json()
    }
    assert {"upload", "confirm", "generate", "download"} <= actions


def test_real_export_zip_download_stale_and_cross_user_denial(tmp_path: Path) -> None:
    client, repository = client_and_repository(tmp_path)
    headers = authorization(OWNER_TOKEN)
    project_id = client.post(
        "/api/v1/projects", json={"name": "Export vertical slice"}, headers=headers
    ).json()["project_id"]
    revision = client.post(
        f"/api/v1/projects/{project_id}/sources",
        json={"kind": "file", "config": {"filename_pattern": "*.csv"}},
        headers=headers,
    ).json()["revision"]
    specification = api_specification(project_id, revision)
    assert (
        client.post(
            f"/api/v1/projects/{project_id}/specification/confirm",
            json=specification.model_dump(mode="json"),
            headers=headers,
        ).status_code
        == 200
    )
    preview = client.post(
        f"/api/v1/projects/{project_id}/preview",
        json={"rows": [{"amount": "10.50"}], "timeout_seconds": 5},
        headers=headers,
    )
    assert preview.status_code == 200

    created = client.post(
        f"/api/v1/projects/{project_id}/exports",
        json={"sample_rows": [{"amount": "10.50"}]},
        headers={**headers, "Idempotency-Key": "vertical-export-1"},
    )
    assert created.status_code == 202
    job_id = created.json()["job_id"]
    assert (
        client.get(f"/api/v1/projects/{project_id}/jobs/{job_id}", headers=headers).json()["status"]
        == "succeeded"
    )
    artifact = client.get(f"/api/v1/projects/{project_id}/artifacts", headers=headers).json()[0]
    assert artifact["artifact_status"] == "sample_tested"
    assert artifact["stale"] is False
    paths = {item["path"] for item in artifact["manifest"]["files"]}
    assert {"pipeline.py", "README.md", ".env.example", "pipeline-spec.json"} <= paths

    duplicate = client.post(
        f"/api/v1/projects/{project_id}/exports",
        json={"sample_rows": [{"amount": "10.50"}]},
        headers={**headers, "Idempotency-Key": "vertical-export-1"},
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["artifact_id"] == artifact["artifact_id"]

    denied_paths = (
        f"/api/v1/projects/{project_id}/specification/versions",
        f"/api/v1/projects/{project_id}/jobs/{job_id}",
        f"/api/v1/projects/{project_id}/artifacts",
        f"/api/v1/projects/{project_id}/artifacts/{artifact['artifact_id']}",
        f"/api/v1/projects/{project_id}/artifacts/{artifact['artifact_id']}/download",
    )
    for path in denied_paths:
        assert client.get(path, headers=authorization(OTHER_TOKEN)).status_code == 404
    downloaded = client.get(
        f"/api/v1/projects/{project_id}/artifacts/{artifact['artifact_id']}/download",
        headers=headers,
    )
    assert downloaded.status_code == 200
    assert downloaded.headers["content-type"] == "application/zip"
    with ZipFile(BytesIO(downloaded.content)) as archive:
        names = set(archive.namelist())
        manifest = archive.read("artifact-manifest.json").decode("utf-8")
        package_text = "\n".join(
            archive.read(name).decode("utf-8") for name in names if not name.endswith(".zip")
        )
    assert {
        "pipeline.py",
        "runtime_core.py",
        "README.md",
        ".env.example",
        "pipeline-spec.json",
        "sample-output.json",
        "artifact-manifest.json",
        "tests/test_pipeline.py",
    } <= names
    assert '"contains_credentials": false' in manifest
    assert OWNER_TOKEN not in package_text
    assert "password=" not in package_text.lower()

    package_root = tmp_path / "clean-package"
    with ZipFile(BytesIO(downloaded.content)) as archive:
        archive.extractall(package_root)
    input_dir = package_root / "incoming"
    input_dir.mkdir()
    (input_dir / "future.csv").write_text("amount\n15.25\n", encoding="utf-8")
    command = [
        sys.executable,
        "pipeline.py",
        "--input-dir",
        str(input_dir),
        "--output-dir",
        str(package_root / "out"),
        "--quarantine-dir",
        str(package_root / "quarantine"),
        "--state-file",
        str(package_root / "state" / "processed.json"),
    ]
    first = subprocess.run(command, cwd=package_root, capture_output=True, text=True, check=False)
    second = subprocess.run(command, cwd=package_root, capture_output=True, text=True, check=False)
    assert first.returncode == 0 and json.loads(first.stdout)["processed"] == 1
    assert second.returncode == 0 and json.loads(second.stdout)["skipped"] == 1

    client.post(
        f"/api/v1/projects/{project_id}/sources",
        json={"kind": "file", "config": {"filename_pattern": "*.json"}},
        headers=headers,
    )
    historical = client.get(
        f"/api/v1/projects/{project_id}/artifacts/{artifact['artifact_id']}", headers=headers
    ).json()
    assert historical["stale"] is True
    assert historical["historical"] is True
    with repository.database.connect() as connection:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM artifacts WHERE project_id=?", (project_id,)
            ).fetchone()[0]
            == 1
        )


def test_logout_permission_change_rate_limit_and_project_data_deletion(tmp_path: Path) -> None:
    client, repository = client_and_repository(tmp_path)
    owner_headers = authorization(OWNER_TOKEN)
    project_id = client.post(
        "/api/v1/projects", json={"name": "Deletion"}, headers=owner_headers
    ).json()["project_id"]
    uploaded = client.post(
        f"/api/v1/projects/{project_id}/file-sources",
        files={"file": ("amounts.csv", b"amount\n10\n", "text/csv")},
        headers=owner_headers,
    ).json()
    sample_ref = repository.get_sample_reference(
        repository.authenticate(OWNER_TOKEN), project_id, uploaded["sample_id"]
    )
    repository.confirm_specification(
        repository.authenticate(OWNER_TOKEN),
        project_id,
        api_specification(project_id, uploaded["revision"]),
    )
    export_job = client.post(
        f"/api/v1/projects/{project_id}/exports",
        json={"sample_rows": []},
        headers={**owner_headers, "Idempotency-Key": "deletion-export"},
    ).json()
    assert export_job["status"] == "running"
    artifact = client.get(f"/api/v1/projects/{project_id}/artifacts", headers=owner_headers).json()[
        0
    ]
    artifact_ref = repository.get_artifact_storage_ref(
        repository.authenticate(OWNER_TOKEN), project_id, artifact["artifact_id"]
    )
    sample_path = tmp_path / "data" / "samples" / sample_ref
    artifact_path = tmp_path / "generated" / Path(artifact_ref)
    assert sample_path.is_file() and artifact_path.is_file()

    repository.add_member(
        repository.authenticate(OWNER_TOKEN), project_id, "api-viewer", Role.EDITOR
    )
    editor_write = client.post(
        f"/api/v1/projects/{project_id}/sources",
        json={"kind": "file", "config": {"filename_pattern": "*.csv"}},
        headers=authorization(VIEWER_TOKEN),
    )
    assert editor_write.status_code == 201
    repository.add_member(
        repository.authenticate(OWNER_TOKEN), project_id, "api-viewer", Role.VIEWER
    )
    viewer_write = client.post(
        f"/api/v1/projects/{project_id}/sources",
        json={"kind": "file", "config": {"filename_pattern": "*.json"}},
        headers=authorization(VIEWER_TOKEN),
    )
    assert viewer_write.status_code == 403

    assert client.delete(f"/api/v1/projects/{project_id}", headers=owner_headers).status_code == 204
    assert not sample_path.exists() and not artifact_path.exists()
    with repository.database.connect() as connection:
        for table in (
            "source_samples",
            "artifacts",
            "jobs",
            "source_configs",
            "specification_revisions",
        ):
            assert (
                connection.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE project_id=?", (project_id,)
                ).fetchone()[0]
                == 0
            )
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM audit_events WHERE project_id=?", (project_id,)
            ).fetchone()[0]
            > 0
        )

    logout_client, _ = client_and_repository(tmp_path / "logout")
    assert logout_client.post("/api/v1/auth/logout", headers=owner_headers).status_code == 204
    assert logout_client.get("/api/v1/projects", headers=owner_headers).status_code == 401

    rate_database = Database(tmp_path / "rate.sqlite3")
    rate_database.migrate()
    rate_repository = Repository(rate_database)
    rate_repository.create_user("rate-user", "Rate User", OWNER_TOKEN)
    rate_app = create_app(
        Settings(
            environment="testing",
            data_dir=tmp_path / "rate-data",
            generated_dir=tmp_path / "rate-generated",
            rate_limit_requests=2,
            rate_limit_window_seconds=60,
        ),
        rate_repository,
    )
    rate_client = TestClient(rate_app, raise_server_exceptions=False)
    assert rate_client.get("/api/v1/projects", headers=owner_headers).status_code == 200
    assert rate_client.get("/api/v1/projects", headers=owner_headers).status_code == 200
    limited = rate_client.get("/api/v1/projects", headers=owner_headers)
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"


def test_api_rejects_invalid_etag(tmp_path: Path) -> None:
    client, _ = client_and_repository(tmp_path)
    project_id = client.post(
        "/api/v1/projects", json={"name": "ETag"}, headers=authorization(OWNER_TOKEN)
    ).json()["project_id"]
    response = client.patch(
        f"/api/v1/projects/{project_id}",
        json={"name": "Nope"},
        headers={**authorization(OWNER_TOKEN), "If-Match": "not-a-number"},
    )
    assert response.status_code == 409


def test_file_upload_api_returns_metadata_without_raw_rows(tmp_path: Path) -> None:
    client, repository = client_and_repository(tmp_path)
    project_id = client.post(
        "/api/v1/projects", json={"name": "Upload"}, headers=authorization(OWNER_TOKEN)
    ).json()["project_id"]
    content = b"customer_id,amount\nC-1,10\nC-2,20\n"
    response = client.post(
        f"/api/v1/projects/{project_id}/file-sources",
        files={"file": ("customers.csv", content, "text/csv")},
        data={"delimiter": ",", "sample_row_limit": "100"},
        headers=authorization(OWNER_TOKEN),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["revision"] == 1
    assert body["analysis"]["runtime"]["filename_pattern"] == "*.csv"
    assert "C-1" not in response.text
    storage_ref = repository.get_sample_reference(
        repository.authenticate(OWNER_TOKEN), project_id, body["sample_id"]
    )
    assert storage_ref != "customers.csv"
    assert (tmp_path / "data" / "samples" / storage_ref).read_bytes() == content


def test_file_upload_authorizes_before_storing(tmp_path: Path) -> None:
    client, _ = client_and_repository(tmp_path)
    project_id = client.post(
        "/api/v1/projects", json={"name": "Private upload"}, headers=authorization(OWNER_TOKEN)
    ).json()["project_id"]
    response = client.post(
        f"/api/v1/projects/{project_id}/file-sources",
        files={"file": ("private.csv", b"id\n1", "text/csv")},
        headers=authorization(OTHER_TOKEN),
    )
    assert response.status_code == 404
    sample_dir = tmp_path / "data" / "samples"
    assert not sample_dir.exists() or list(sample_dir.iterdir()) == []


def test_database_source_api_authorizes_tests_catalog_and_sample(tmp_path: Path) -> None:
    client, repository = client_and_repository(tmp_path)
    connector = AsyncMock(spec=DatabaseConnectorService)
    connector.max_sample_rows = 100
    connector.test_connection.return_value = None
    connector.catalog.return_value = DatabaseCatalog(
        schemas=("public",),
        objects=(DatabaseObject(schema_name="public", object_name="orders", object_type="table"),),
    )
    connector.sample.return_value = DatabaseSample(
        columns=("order_id",),
        rows=({"order_id": 1},),
        truncated=False,
        source={
            "database_type": "postgresql",
            "host": "***",
            "database": "***",
            "username": "***",
            "connection_ref": "secret://***",
            "port": 5432,
            "tls_mode": "verify_identity",
        },
    )
    client.app.state.database_connectors = connector
    project_id = client.post(
        "/api/v1/projects", json={"name": "Database"}, headers=authorization(OWNER_TOKEN)
    ).json()["project_id"]
    connection_body = {
        "database_type": "postgresql",
        "host": "db.example.com",
        "port": 5432,
        "database": "analytics",
        "username": "reader",
        "connection_ref": "secret://warehouse/read-only",
        "tls_mode": "verify_identity",
    }

    unauthorized = client.post(
        f"/api/v1/projects/{project_id}/database-sources/test",
        json=connection_body,
        headers=authorization(OTHER_TOKEN),
    )
    assert unauthorized.status_code == 404
    connector.test_connection.assert_not_awaited()

    tested = client.post(
        f"/api/v1/projects/{project_id}/database-sources/test",
        json=connection_body,
        headers=authorization(OWNER_TOKEN),
    )
    assert tested.status_code == 204
    catalog = client.post(
        f"/api/v1/projects/{project_id}/database-sources/catalog",
        json=connection_body,
        headers=authorization(OWNER_TOKEN),
    )
    assert catalog.json()["objects"][0]["object_name"] == "orders"

    analyzed = client.post(
        f"/api/v1/projects/{project_id}/database-sources/analyze",
        json={
            "connection": connection_body,
            "schema_name": "public",
            "object_name": "orders",
            "sample_limit": 50,
        },
        headers=authorization(OWNER_TOKEN),
    )
    assert analyzed.status_code == 201
    assert analyzed.json()["revision"] == 1
    assert "db.example.com" not in analyzed.text
    assert "reader" not in analyzed.text
    assert "warehouse/read-only" not in analyzed.text
    with repository.database.connect() as database:
        saved = str(database.execute("SELECT config_json FROM source_configs").fetchone()[0])
    assert "secret://warehouse/read-only" in saved
    assert "password" not in saved.lower()


def test_profile_confirm_requirement_and_specification_workflow(tmp_path: Path) -> None:
    client, repository = client_and_repository(tmp_path)
    project_id = client.post(
        "/api/v1/projects",
        json={"name": "Profile to specification"},
        headers=authorization(OWNER_TOKEN),
    ).json()["project_id"]
    uploaded = client.post(
        f"/api/v1/projects/{project_id}/file-sources",
        files={
            "file": (
                "orders.csv",
                b"customer_id,amount,email\nC-1,10.5,one@example.com\nC-2,20.5,two@example.com\n",
                "text/csv",
            )
        },
        headers=authorization(OWNER_TOKEN),
    )
    assert uploaded.status_code == 201
    profile = uploaded.json()["profile"]
    assert "one@example.com" not in uploaded.text
    assert profile["fields"][2]["sensitive_category"] == "email"
    schema_response = client.get(
        f"/api/v1/projects/{project_id}/schema", headers=authorization(OWNER_TOKEN)
    )
    assert schema_response.json()["confirmed"] is None

    confirmed_fields = []
    for field in profile["fields"]:
        confirmed_fields.append(
            {
                "name": field["name"],
                "inferred_type": field["inferred_type"],
                "confirmed_type": field["inferred_type"],
                "nullable": field["nullable"],
                "required": field["required"],
                "selected": True,
                "confidence": field["confidence"],
                "null_percentage": field["null_percentage"],
                "distinct_count": field["distinct_count"],
                "pii_classification": field["pii_classification"],
                "samples_masked": field["samples_masked"],
            }
        )
    next(field for field in confirmed_fields if field["name"] == "email")["pii_classification"] = (
        "none"
    )
    confirmed = client.post(
        f"/api/v1/projects/{project_id}/schema/confirm",
        json={"fields": confirmed_fields},
        headers=authorization(OWNER_TOKEN),
    )
    assert confirmed.status_code == 200
    assert len(confirmed.json()["schema_fingerprint"]) == 64
    confirmed_schema = client.get(
        f"/api/v1/projects/{project_id}/schema", headers=authorization(OWNER_TOKEN)
    ).json()["confirmed"]
    confirmed_email = next(
        field for field in confirmed_schema["fields"] if field["name"] == "email"
    )
    assert confirmed_email["pii_classification"] == "possible"

    interpreter = AsyncMock(spec=RequirementInterpreter)
    interpreter.analyze.return_value = AIProviderResult(
        analysis=RequirementAnalysis(
            schema_version="1.0",
            status="ready",
            transformations=(
                TransformationDraft(
                    rule_id="rename_customer",
                    order=1,
                    kind="rename",
                    inputs=("customer_id",),
                    output="customer_key",
                    parameters={},
                ),
            ),
            validations=(
                ValidationDraft(
                    rule_id="amount_positive",
                    field="amount",
                    kind="range",
                    parameters={"minimum": 0},
                ),
            ),
            confidence=0.9,
            warnings=("Email will be masked before output.",),
            assumptions=("One row represents one order.",),
            clarification_questions=(),
        ),
        model="local-test-llama",
        metrics=InferenceMetrics(total_seconds=0.1),
    )
    client.app.state.requirement_interpreter = interpreter
    proposed = client.post(
        f"/api/v1/projects/{project_id}/requirement-proposals",
        json={
            "requirement": "เปลี่ยน customer_id และตรวจสอบ amount ให้มากกว่าศูนย์",
            "language_hint": "th",
        },
        headers=authorization(OWNER_TOKEN),
    )
    assert proposed.status_code == 201
    proposal_id = proposed.json()["proposal_id"]
    assert proposed.json()["requires_confirmation"] is True
    ai_request = interpreter.analyze.await_args.args[0]
    assert not hasattr(ai_request, "rows")
    assert {field.name for field in ai_request.available_fields} == {
        "customer_id",
        "amount",
        "email",
    }

    confirmation_body = {
        "proposal_id": proposal_id,
        "name": "orders-pipeline",
        "transformations": [
            {
                "rule_id": "rename_customer",
                "order": 1,
                "kind": "rename",
                "inputs": ["customer_id"],
                "output": "customer_key",
                "parameters": {},
            },
            {
                "rule_id": "mask_email",
                "order": 2,
                "kind": "mask",
                "inputs": ["email"],
                "output": None,
                "parameters": {"strategy": "email"},
            },
        ],
        "validations": [
            {
                "rule_id": "amount_positive",
                "field": "amount",
                "kind": "range",
                "severity": "error",
                "parameters": {"minimum": 0},
            }
        ],
        "output": {"format": "csv"},
        "target": {"language": "python"},
        "assumptions_acknowledged": False,
    }
    unacknowledged = client.post(
        f"/api/v1/projects/{project_id}/specification/confirm-from-proposal",
        json=confirmation_body,
        headers=authorization(OWNER_TOKEN),
    )
    assert unacknowledged.status_code == 409
    assert unacknowledged.json()["error"]["code"] == "CONFIRMATION_REQUIRED"

    confirmation_body["assumptions_acknowledged"] = True
    specification = client.post(
        f"/api/v1/projects/{project_id}/specification/confirm-from-proposal",
        json=confirmation_body,
        headers=authorization(OWNER_TOKEN),
    )
    assert specification.status_code == 200
    assert specification.json()["confirmed"] is True
    versions = client.get(
        f"/api/v1/projects/{project_id}/specification/versions",
        headers=authorization(OWNER_TOKEN),
    ).json()
    assert versions[0]["revision"] == 1
    assert (
        repository.get_project(repository.authenticate(OWNER_TOKEN), project_id).status
        == "confirmed"
    )
