"""Persistence, authorization, migration, and job recovery tests."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from pae.domain.enums import (
    DataType,
    OutputFormat,
    PiiClassification,
    ProjectStatus,
    TargetLanguage,
)
from pae.domain.models import (
    FieldDefinition,
    FileDiscoveryContract,
    FileSource,
    OutputContract,
    PipelineSpecification,
    TargetRuntime,
)
from pae.jobs import JobExecutionResult, JobWorker, RetryableJobError
from pae.persistence.database import MIGRATIONS, Database
from pae.persistence.errors import (
    AuthenticationRequired,
    CapacityLimit,
    InvalidStateTransition,
    PermissionDenied,
    ResourceNotFound,
    RevisionConflict,
    SecretValueRejected,
)
from pae.persistence.models import Permission, Principal, Role
from pae.persistence.repository import Repository

OWNER_TOKEN = "owner-token-with-32-characters-000"
EDITOR_TOKEN = "editor-token-with-32-characters-00"
OTHER_TOKEN = "other-token-with-32-characters-000"


@pytest.fixture
def database(tmp_path: Path) -> Database:
    value = Database(tmp_path / "pae.sqlite3")
    value.migrate()
    return value


@pytest.fixture
def repository(database: Database) -> Repository:
    value = Repository(database, queue_capacity=3)
    value.create_user("owner", "Owner", OWNER_TOKEN)
    value.create_user("editor", "Editor", EDITOR_TOKEN)
    value.create_user("other", "Other", OTHER_TOKEN)
    return value


@pytest.fixture
def owner() -> Principal:
    return Principal("owner", "Owner")


def specification(project_id: str, revision: int) -> PipelineSpecification:
    return PipelineSpecification(
        specification_id=uuid4(),
        project_id=UUID(project_id),
        revision=revision,
        name=f"transactions-v{revision}",
        source_fingerprint=f"{revision:x}" * 64,
        sources=(
            FileSource(
                source_id="transactions",
                file_format="csv",
                original_name="sample.csv",
                runtime=FileDiscoveryContract(filename_pattern="*.csv"),
            ),
        ),
        fields=(
            FieldDefinition(
                source_id="transactions",
                source_name="amount",
                target_name="amount",
                inferred_type=DataType.DECIMAL,
                confirmed_type=DataType.DECIMAL,
                nullable=False,
                confidence=1,
                null_percentage=0,
                pii_classification=PiiClassification.NONE,
            ),
        ),
        output=OutputContract(format=OutputFormat.CSV),
        target=TargetRuntime(language=TargetLanguage.PYTHON),
        confirmed_by="owner",
        confirmed_at=datetime.now(UTC),
    )


def confirmed_project(repository: Repository, owner: Principal) -> str:
    project = repository.create_project(owner, "Transactions")
    revision = repository.save_source_config(
        owner,
        project.project_id,
        "file",
        {"connection_ref": "local://incoming", "filename_pattern": "*.csv"},
    )
    repository.confirm_specification(
        owner, project.project_id, specification(project.project_id, revision)
    )
    return project.project_id


def test_migrations_support_fresh_install_upgrade_and_failed_recovery(tmp_path: Path) -> None:
    database = Database(tmp_path / "upgrade.sqlite3")
    database.migrate(MIGRATIONS[:1])
    with database.connect() as connection:
        assert connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0] == 1
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE name='validation_results'"
            ).fetchone()[0]
            == 0
        )

    database.migrate()
    with database.connect() as connection:
        assert connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[
            0
        ] == len(MIGRATIONS)

    bad_migrations = (*MIGRATIONS, "CREATE TABLE should_rollback(x); INVALID STATEMENT;")
    with pytest.raises(sqlite3.Error):
        database.migrate(bad_migrations)
    with database.connect() as connection:
        assert connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[
            0
        ] == len(MIGRATIONS)
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE name='should_rollback'"
            ).fetchone()[0]
            == 0
        )


def test_tokens_are_hashed_and_authentication_is_constant_result_shape(
    repository: Repository, database: Database
) -> None:
    assert repository.authenticate(OWNER_TOKEN).user_id == "owner"
    with database.connect() as connection:
        stored = str(
            connection.execute("SELECT token_hash FROM users WHERE user_id='owner'").fetchone()[0]
        )
    assert stored != OWNER_TOKEN
    assert len(stored) == 64
    with pytest.raises(AuthenticationRequired):
        repository.authenticate("invalid-token-value")
    with pytest.raises(ValueError, match="16"):
        repository.create_user("short", "Short", "tiny")


def test_project_crud_optimistic_locking_and_cross_user_isolation(
    repository: Repository, owner: Principal
) -> None:
    project = repository.create_project(owner, "Original")
    assert repository.list_projects(owner)[0].project_id == project.project_id
    updated = repository.update_project(
        owner, project.project_id, "Renamed", project.record_version
    )
    assert updated.name == "Renamed"
    assert updated.updated_by == owner.user_id
    with pytest.raises(RevisionConflict):
        repository.update_project(owner, project.project_id, "Stale", project.record_version)
    with pytest.raises(ResourceNotFound):
        repository.get_project(Principal("other", "Other"), project.project_id)
    repository.delete_project(owner, project.project_id)
    with pytest.raises(ResourceNotFound):
        repository.get_project(owner, project.project_id)


def test_role_permissions_are_enforced_at_resource_level(
    repository: Repository, owner: Principal
) -> None:
    project = repository.create_project(owner, "Shared")
    editor = Principal("editor", "Editor")
    repository.add_member(owner, project.project_id, editor.user_id, Role.EDITOR)
    edited = repository.update_project(editor, project.project_id, "Edited", 1)
    assert edited.name == "Edited"
    with pytest.raises(PermissionDenied):
        repository.delete_project(editor, project.project_id)
    with pytest.raises(PermissionDenied):
        repository.add_member(owner, project.project_id, "other", Role.OWNER)
    with pytest.raises(ResourceNotFound):
        repository.add_member(owner, project.project_id, "missing-user", Role.VIEWER)
    assert repository.get_project(editor, project.project_id, Permission.VIEW).project_id


def test_source_configuration_rejects_plaintext_secrets_and_invalidates_revision(
    repository: Repository, owner: Principal
) -> None:
    project = repository.create_project(owner, "Secure source")
    with pytest.raises(SecretValueRejected):
        repository.save_source_config(
            owner, project.project_id, "database", {"nested": {"password": "not-safe"}}
        )
    with pytest.raises(SecretValueRejected):
        repository.save_source_config(
            owner, project.project_id, "database", {"options": [{"token": "not-safe"}]}
        )
    with pytest.raises(SecretValueRejected):
        repository.save_source_config(
            owner, project.project_id, "database", {"db_password": "not-safe"}
        )
    with pytest.raises(SecretValueRejected):
        repository.save_source_config(
            owner,
            project.project_id,
            "database",
            {"endpoint": "postgresql://reader:plain-password@localhost/orders"},
        )
    revision = repository.save_source_config(
        owner,
        project.project_id,
        "database",
        {"connection_ref": "secret://warehouse/read-only", "object_name": "orders"},
    )
    repository.confirm_specification(
        owner, project.project_id, specification(project.project_id, revision)
    )
    next_revision = repository.save_source_config(
        owner,
        project.project_id,
        "database",
        {"connection_ref": "secret://warehouse/read-only", "object_name": "orders_v2"},
    )
    current = repository.get_project(owner, project.project_id)
    assert next_revision == 2
    assert current.status == "source_ready"
    assert current.specification_confirmed is False


def test_specification_history_is_immutable(repository: Repository, owner: Principal) -> None:
    project_id = confirmed_project(repository, owner)
    repository.save_source_config(
        owner, project_id, "file", {"connection_ref": "local://v2", "filename_pattern": "*.csv"}
    )
    repository.confirm_specification(owner, project_id, specification(project_id, 2))
    versions = repository.list_specification_versions(owner, project_id)
    assert [item.revision for item in versions] == [2, 1]
    with (
        repository.database.connect() as connection,
        pytest.raises(sqlite3.IntegrityError, match="immutable"),
    ):
        connection.execute(
            "UPDATE specification_revisions SET specification_json='{}' "
            "WHERE project_id=? AND revision=1",
            (project_id,),
        )


def test_specification_confirmation_rejects_mismatch_stale_and_duplicate(
    repository: Repository, owner: Principal
) -> None:
    project = repository.create_project(owner, "Revision checks")
    revision = repository.save_source_config(
        owner, project.project_id, "file", {"connection_ref": "local://one"}
    )
    with pytest.raises(RevisionConflict, match="does not match"):
        repository.confirm_specification(
            owner, project.project_id, specification(str(uuid4()), revision)
        )
    with pytest.raises(RevisionConflict, match="stale"):
        repository.confirm_specification(
            owner, project.project_id, specification(project.project_id, revision + 1)
        )
    valid = specification(project.project_id, revision)
    repository.confirm_specification(owner, project.project_id, valid)
    with pytest.raises(RevisionConflict, match="already exists"):
        repository.confirm_specification(owner, project.project_id, valid)


def test_job_idempotency_capacity_concurrency_and_success(
    repository: Repository, owner: Principal
) -> None:
    project_id = confirmed_project(repository, owner)
    first, created = repository.submit_job(
        owner, project_id, "generation", "same-key", generator_version="0.1.0"
    )
    duplicate, duplicate_created = repository.submit_job(
        owner, project_id, "generation", "same-key", generator_version="0.1.0"
    )
    assert created is True
    assert duplicate_created is False
    assert duplicate.job_id == first.job_id

    repository.submit_job(owner, project_id, "preview", "two", generator_version="0.1.0")
    repository.submit_job(owner, project_id, "analysis", "three", generator_version="0.1.0")
    with pytest.raises(CapacityLimit):
        repository.submit_job(owner, project_id, "execute", "four", generator_version="0.1.0")

    running = repository.claim_next_job("worker-1", concurrency_limit=1)
    assert running is not None and running.status == "running"
    assert repository.claim_next_job("worker-2", concurrency_limit=1) is None
    repository.report_progress(running.job_id, 50)
    completed = repository.complete_job(
        running.job_id, {"artifact": "bundle"}, {"syntax": "passed"}, validation_passed=True
    )
    assert completed.status == "succeeded"
    assert completed.progress_percentage == 100
    assert repository.get_job_validation(owner, project_id, running.job_id) == {
        "passed": True,
        "result": {"syntax": "passed"},
    }
    with pytest.raises(InvalidStateTransition):
        repository.complete_job(running.job_id, {"second": True}, {}, validation_passed=True)

    with repository.database.connect() as connection:
        artifact_id = str(
            connection.execute(
                "SELECT artifact_id FROM artifacts WHERE job_id=?", (running.job_id,)
            ).fetchone()[0]
        )
    manifest = repository.get_artifact_manifest(owner, project_id, artifact_id)
    assert manifest["revision"] == 1
    assert manifest["manifest"] == {"artifact": "bundle"}
    with pytest.raises(ResourceNotFound):
        repository.get_artifact_manifest(Principal("other", "Other"), project_id, artifact_id)


def test_samples_jobs_versions_and_downloads_enforce_project_boundary(
    repository: Repository, owner: Principal
) -> None:
    project_id = confirmed_project(repository, owner)
    sample_id = repository.register_sample_reference(
        owner, project_id, "encrypted://samples/one", datetime(2026, 10, 1, tzinfo=UTC)
    )
    assert repository.get_sample_reference(owner, project_id, sample_id).startswith("encrypted://")
    expired_id = repository.register_sample_reference(
        owner,
        project_id,
        "encrypted://samples/expired",
        datetime.now(UTC) - timedelta(seconds=1),
    )
    with pytest.raises(ResourceNotFound):
        repository.get_sample_reference(owner, project_id, expired_id)
    other = Principal("other", "Other")
    with pytest.raises(ResourceNotFound):
        repository.get_sample_reference(other, project_id, sample_id)
    with pytest.raises(ResourceNotFound):
        repository.list_specification_versions(other, project_id)

    job, _ = repository.submit_job(
        owner, project_id, "generation", "artifact", generator_version="0.1.0"
    )
    repository.claim_next_job("artifact-worker")
    repository.complete_job(job.job_id, {"files": ["pipeline.py"]}, {}, validation_passed=True)
    with repository.database.connect() as connection:
        artifact_id = str(connection.execute("SELECT artifact_id FROM artifacts").fetchone()[0])
    authorized = repository.authorize_artifact_download(owner, project_id, artifact_id)
    assert authorized["manifest"] == {"files": ["pipeline.py"]}
    with pytest.raises(ResourceNotFound):
        repository.authorize_artifact_download(other, project_id, artifact_id)
    with pytest.raises(ResourceNotFound):
        repository.get_job(other, project_id, job.job_id)


def test_old_job_cannot_commit_after_source_revision_changes(
    repository: Repository, owner: Principal, database: Database
) -> None:
    project_id = confirmed_project(repository, owner)
    job, _ = repository.submit_job(
        owner, project_id, "generation", "old-revision", generator_version="0.1.0"
    )
    repository.claim_next_job("worker")
    repository.save_source_config(
        owner, project_id, "file", {"connection_ref": "local://new", "filename_pattern": "*.csv"}
    )
    stale = repository.complete_job(job.job_id, {"bad": True}, {}, validation_passed=True)
    assert stale.status == "failed"
    assert stale.error_code == "STALE_REVISION"
    with database.connect() as connection:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM job_results WHERE job_id=?", (job.job_id,)
            ).fetchone()[0]
            == 0
        )


def test_worker_retries_recovers_and_cancels(repository: Repository, owner: Principal) -> None:
    project_id = confirmed_project(repository, owner)
    job, _ = repository.submit_job(
        owner,
        project_id,
        "generation",
        "retry",
        generator_version="0.1.0",
        max_attempts=2,
    )
    worker = JobWorker(repository, worker_id="worker")

    def transient(_: object) -> JobExecutionResult:
        raise RetryableJobError("TEMPORARY")

    retried = worker.run_once(transient)
    assert retried is not None and retried.status == "queued"
    claimed = repository.claim_next_job("crashed-worker")
    assert claimed is not None and claimed.attempt == 2
    recovered, failed = repository.recover_interrupted_jobs()
    assert (recovered, failed) == (0, 1)
    assert repository.get_job(owner, project_id, job.job_id).status == "failed"

    cancelled, _ = repository.submit_job(
        owner, project_id, "preview", "cancel", generator_version="0.1.0"
    )
    assert repository.cancel_job(owner, project_id, cancelled.job_id).status == "cancelled"


def test_job_failure_validation_cancellation_and_progress_guards(
    repository: Repository, owner: Principal
) -> None:
    project_id = confirmed_project(repository, owner)
    assert repository.claim_next_job("idle") is None
    with pytest.raises(ResourceNotFound):
        repository.report_progress(str(uuid4()), 1)
    with pytest.raises(ValueError):
        repository.report_progress(str(uuid4()), 100)
    with pytest.raises(ResourceNotFound):
        repository.get_job(owner, project_id, str(uuid4()))
    with pytest.raises(ResourceNotFound):
        repository.cancel_job(owner, project_id, str(uuid4()))
    with pytest.raises(ResourceNotFound):
        repository.complete_job(str(uuid4()), {}, {}, validation_passed=True)
    with pytest.raises(ResourceNotFound):
        repository.fail_job(str(uuid4()), "MISSING", retryable=False)

    validation_job, _ = repository.submit_job(
        owner, project_id, "preview", "validation", generator_version="0.1.0"
    )
    repository.claim_next_job("validation-worker")
    repository.report_progress(validation_job.job_id, 40)
    with pytest.raises(InvalidStateTransition, match="backwards"):
        repository.report_progress(validation_job.job_id, 30)
    failed = repository.complete_job(
        validation_job.job_id, {}, {"reason": "bad"}, validation_passed=False
    )
    assert failed.error_code == "VALIDATION_FAILED"
    with pytest.raises(InvalidStateTransition):
        repository.report_progress(validation_job.job_id, 50)
    with pytest.raises(InvalidStateTransition):
        repository.fail_job(validation_job.job_id, "DONE", retryable=False)
    assert repository.cancel_job(owner, project_id, validation_job.job_id).status == "failed"

    cancelled_job, _ = repository.submit_job(
        owner, project_id, "generation", "running-cancel", generator_version="0.1.0"
    )
    repository.claim_next_job("cancel-worker")
    assert repository.cancel_job(owner, project_id, cancelled_job.job_id).status == "cancelling"
    cancelled = repository.complete_job(cancelled_job.job_id, {}, {}, validation_passed=True)
    assert cancelled.status == "cancelled"
    assert cancelled.error_code == "CANCELLED_BY_USER"


def test_recovery_retry_branch_and_worker_terminal_error(
    repository: Repository, owner: Principal
) -> None:
    project_id = confirmed_project(repository, owner)
    recoverable, _ = repository.submit_job(
        owner,
        project_id,
        "analysis",
        "recoverable",
        generator_version="0.1.0",
        max_attempts=3,
    )
    repository.claim_next_job("crashed")
    assert repository.recover_interrupted_jobs() == (1, 0)
    assert repository.get_job(owner, project_id, recoverable.job_id).status == "queued"

    worker = JobWorker(repository, worker_id="terminal-worker")

    def terminal(_: object) -> JobExecutionResult:
        raise RuntimeError("terminal")

    terminal_result = worker.run_once(terminal)
    assert terminal_result is not None and terminal_result.status == "failed"

    success_job, _ = repository.submit_job(
        owner, project_id, "preview", "worker-success", generator_version="0.1.0"
    )
    success = worker.run_once(
        lambda _: JobExecutionResult(
            result={"ok": True}, validation_result={"ok": True}, validation_passed=True
        )
    )
    assert success is not None and success.job_id == success_job.job_id
    assert success.status == "succeeded"


def test_audit_log_covers_workflow_actions(repository: Repository, owner: Principal) -> None:
    project_id = confirmed_project(repository, owner)
    for action in ("analyze", "execute", "download"):
        repository.record_audit_event(owner, project_id, action, "workflow")
    actions = {event["action"] for event in repository.list_audit_events(owner, project_id)}
    assert {"project.create", "upload", "confirm", "analyze", "execute", "download"} <= actions


def test_invalid_status_transition_fails_closed(repository: Repository, owner: Principal) -> None:
    project = repository.create_project(owner, "Workflow")
    transitioned = repository.transition_project(
        owner, project.project_id, target=ProjectStatus.SOURCE_READY
    )
    assert transitioned.status == "source_ready"
    with pytest.raises(InvalidStateTransition):
        repository.transition_project(owner, project.project_id, target=ProjectStatus.READY)


def test_missing_sample_validation_artifact_and_unconfirmed_job_fail_closed(
    repository: Repository, owner: Principal
) -> None:
    project = repository.create_project(owner, "Missing resources")
    with pytest.raises(InvalidStateTransition, match="confirmed"):
        repository.submit_job(
            owner, project.project_id, "generation", "no-spec", generator_version="0.1.0"
        )
    with pytest.raises(ResourceNotFound):
        repository.get_sample_reference(owner, project.project_id, str(uuid4()))
    with pytest.raises(ResourceNotFound):
        repository.get_artifact_manifest(owner, project.project_id, str(uuid4()))
