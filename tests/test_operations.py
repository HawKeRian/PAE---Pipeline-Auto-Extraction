"""Readiness, metrics, backup, restore, and release-operation tests."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from pae.backup import create_backup, restore_backup
from pae.config import Settings
from pae.main import create_app
from pae.observability import AlertDispatcher
from pae.persistence.database import Database
from pae.persistence.repository import Repository


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_readiness_metrics_security_headers_and_alert_delivery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = Database(tmp_path / "pae.sqlite3")
    database.migrate()
    repository = Repository(database)
    monkeypatch.setattr(
        repository,
        "operational_status",
        lambda: {"queued": 15, "running": 1, "failed": 2},
    )
    delivered_payloads: list[dict[str, object]] = []

    def receive_alert(request: httpx.Request) -> httpx.Response:
        delivered_payloads.append(json.loads(request.content))
        return httpx.Response(204)

    alert_client = AsyncClient(transport=httpx.MockTransport(receive_alert))
    application = create_app(
        Settings(
            environment="production",
            data_dir=tmp_path / "data",
            generated_dir=tmp_path / "generated",
            structured_logging=False,
            alert_webhook_url="https://alerts.test/pae",
            alert_webhook_cooldown_seconds=300,
        ),
        repository,
        alert_client,
    )
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="https://test") as client:
        assert (await client.get("/health")).status_code == 200
        ready = await client.get("/ready")
        repeated = await client.get("/ready")
        metrics = await client.get("/metrics")
    await alert_client.aclose()
    assert ready.status_code == 200
    assert ready.json()["components"]["persistence"]["status"] == "ok"
    assert ready.json()["components"]["local_model"]["status"] == "optional_not_checked"
    assert ready.headers["strict-transport-security"].startswith("max-age=")
    assert "pae_http_requests_total" in metrics.text
    assert ready.json()["alerts"] == ["job_queue_depth_high"]
    assert ready.json()["alert_delivery"] == "delivered"
    assert repeated.json()["alert_delivery"] == "throttled"
    assert delivered_payloads[0]["alerts"] == ["job_queue_depth_high"]
    assert delivered_payloads[0]["context"] == {
        "environment": "production",
        "queue": {"queued": 15, "running": 1, "failed": 2},
        "service": "Pipeline Auto Extraction",
    }
    assert "pae_job_queue_depth 15" in metrics.text
    assert 'pae_alert_delivery_total{status="delivered"} 1' in metrics.text
    assert 'pae_alert_delivery_total{status="throttled"} 1' in metrics.text
    assert "pae_process_resident_memory_bytes" in metrics.text


@pytest.mark.anyio
async def test_alert_delivery_failure_is_bounded_and_safe() -> None:
    requests: list[httpx.Request] = []

    def reject_alert(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(503)

    client = AsyncClient(transport=httpx.MockTransport(reject_alert))
    dispatcher = AlertDispatcher(
        "https://alerts.test/pae",
        timeout_seconds=1,
        cooldown_seconds=300,
        client=client,
    )
    assert await dispatcher.deliver(["model_unavailable"], {"environment": "testing"}) == "failed"
    repeated = await dispatcher.deliver(["model_unavailable"], {"environment": "testing"})
    assert repeated == "throttled"
    await client.aclose()
    assert len(requests) == 1
    assert b"token" not in requests[0].content.lower()


def test_alert_webhook_requires_https() -> None:
    with pytest.raises(ValidationError, match="must use https"):
        Settings(alert_webhook_url="http://alerts.test/pae")


def test_backup_restore_integrity_and_empty_target_guard(tmp_path: Path) -> None:
    source = tmp_path / "source"
    database_path = source / "pae.sqlite3"
    database = Database(database_path)
    database.migrate()
    repository = Repository(database)
    repository.create_user("backup-user", "Backup User", "backup-token-with-32-characters-000")
    principal = repository.authenticate("backup-token-with-32-characters-000")
    project = repository.create_project(principal, "Backup project")
    samples = source / "samples"
    artifacts = source / "artifacts"
    samples.mkdir()
    (samples / "sample.bin").write_bytes(b"bounded-sample")
    (artifacts / project.project_id).mkdir(parents=True)
    (artifacts / project.project_id / "artifact.zip").write_bytes(b"artifact")

    archive = tmp_path / "backup.zip"
    manifest = create_backup(database_path, samples, artifacts, archive)
    assert manifest["contains_environment_secrets"] is False
    assert archive.is_file()

    restore_root = tmp_path / "restore"
    restored_database = restore_root / "pae.sqlite3"
    restored_samples = restore_root / "samples"
    restored_artifacts = restore_root / "artifacts"
    restored = restore_backup(archive, restored_database, restored_samples, restored_artifacts)
    assert restored["format_version"] == "1.0"
    assert (restored_samples / "sample.bin").read_bytes() == b"bounded-sample"
    assert (restored_artifacts / project.project_id / "artifact.zip").read_bytes() == b"artifact"
    with sqlite3.connect(restored_database) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute("SELECT name FROM projects").fetchone()[0] == "Backup project"
    with pytest.raises(FileExistsError):
        restore_backup(archive, restored_database, restored_samples, restored_artifacts)
