"""Authorized project, revision, audit, and job persistence operations."""

from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
from datetime import UTC, datetime
from typing import Any, cast
from urllib.parse import urlsplit
from uuid import uuid4

from pae.domain.enums import JobStatus, PiiClassification, ProjectStatus
from pae.domain.fingerprints import model_fingerprint
from pae.domain.models import PipelineSpecification
from pae.persistence.database import Database
from pae.persistence.errors import (
    AuthenticationRequired,
    CapacityLimit,
    InvalidStateTransition,
    PermissionDenied,
    ResourceNotFound,
    RevisionConflict,
    SecretValueRejected,
)
from pae.persistence.models import (
    ROLE_PERMISSION,
    JobView,
    Permission,
    Principal,
    ProjectView,
    Role,
)
from pae.profiling.models import ConfirmedField, ConfirmedSchema, SchemaConfirmation

_FORBIDDEN_SECRET_KEYS = {"password", "secret", "token", "api_key", "connection_uri"}
_ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    ProjectStatus.DRAFT: frozenset({ProjectStatus.SOURCE_READY}),
    ProjectStatus.SOURCE_READY: frozenset(
        {ProjectStatus.ANALYZED, ProjectStatus.AWAITING_CONFIRMATION}
    ),
    ProjectStatus.ANALYZED: frozenset({ProjectStatus.AWAITING_CONFIRMATION}),
    ProjectStatus.AWAITING_CONFIRMATION: frozenset({ProjectStatus.CONFIRMED}),
    ProjectStatus.CONFIRMED: frozenset({ProjectStatus.GENERATING, ProjectStatus.SOURCE_READY}),
    ProjectStatus.GENERATING: frozenset(
        {ProjectStatus.READY, ProjectStatus.FAILED, ProjectStatus.SOURCE_READY}
    ),
    ProjectStatus.READY: frozenset({ProjectStatus.GENERATING, ProjectStatus.SOURCE_READY}),
    ProjectStatus.FAILED: frozenset({ProjectStatus.GENERATING, ProjectStatus.SOURCE_READY}),
}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class Repository:
    """Fail-closed storage API with authorization at every project boundary."""

    def __init__(self, database: Database, *, queue_capacity: int = 20) -> None:
        self.database = database
        self.queue_capacity = queue_capacity

    def create_user(self, user_id: str, display_name: str, token: str) -> Principal:
        if len(token) < 16:
            raise ValueError("authentication token must contain at least 16 characters")
        timestamp = _now()
        with self.database.transaction() as connection:
            connection.execute(
                "INSERT INTO users(user_id, display_name, token_hash, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(user_id) DO UPDATE SET display_name=excluded.display_name, "
                "token_hash=excluded.token_hash, active=1, updated_at=excluded.updated_at",
                (user_id, display_name, _token_hash(token), timestamp, timestamp),
            )
        return Principal(user_id=user_id, display_name=display_name)

    def authenticate(self, token: str) -> Principal:
        candidate = _token_hash(token)
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT user_id, display_name, token_hash FROM users WHERE active=1"
            ).fetchall()
        for row in rows:
            if hmac.compare_digest(str(row["token_hash"]), candidate):
                return Principal(user_id=str(row["user_id"]), display_name=str(row["display_name"]))
        raise AuthenticationRequired("A valid bearer token is required.")

    def deactivate_user(self, principal: Principal) -> None:
        """Revoke the current bearer token immediately."""

        with self.database.transaction() as connection:
            connection.execute(
                "UPDATE users SET active=0, updated_at=? WHERE user_id=?",
                (_now(), principal.user_id),
            )

    def create_project(self, principal: Principal, name: str) -> ProjectView:
        project_id = str(uuid4())
        timestamp = _now()
        with self.database.transaction() as connection:
            connection.execute(
                "INSERT INTO projects(project_id, owner_id, name, status, created_by, "
                "updated_by, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    project_id,
                    principal.user_id,
                    name,
                    ProjectStatus.DRAFT,
                    principal.user_id,
                    principal.user_id,
                    timestamp,
                    timestamp,
                ),
            )
            connection.execute(
                "INSERT INTO project_members(project_id, user_id, role, created_by, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (project_id, principal.user_id, Role.OWNER, principal.user_id, timestamp),
            )
            self._audit(
                connection, principal.user_id, project_id, "project.create", "project", project_id
            )
        return self.get_project(principal, project_id)

    def list_projects(self, principal: Principal) -> tuple[ProjectView, ...]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT p.* FROM projects p JOIN project_members m ON m.project_id=p.project_id "
                "WHERE m.user_id=? AND p.deleted_at IS NULL ORDER BY p.created_at",
                (principal.user_id,),
            ).fetchall()
        return tuple(self._project_view(row) for row in rows)

    def get_project(
        self,
        principal: Principal,
        project_id: str,
        permission: Permission = Permission.VIEW,
    ) -> ProjectView:
        with self.database.connect() as connection:
            row = self._authorized_project(connection, principal, project_id, permission)
        return self._project_view(row)

    def update_project(
        self, principal: Principal, project_id: str, name: str, expected_version: int
    ) -> ProjectView:
        timestamp = _now()
        with self.database.transaction() as connection:
            row = self._authorized_project(connection, principal, project_id, Permission.EDIT)
            if int(row["record_version"]) != expected_version:
                raise RevisionConflict("Project was changed by another request.")
            connection.execute(
                "UPDATE projects SET name=?, record_version=record_version+1, updated_by=?, "
                "updated_at=? WHERE project_id=?",
                (name, principal.user_id, timestamp, project_id),
            )
            self._audit(
                connection, principal.user_id, project_id, "project.update", "project", project_id
            )
        return self.get_project(principal, project_id)

    def delete_project(
        self, principal: Principal, project_id: str
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """Delete project-controlled data while retaining an anonymized audit tombstone."""

        timestamp = _now()
        with self.database.transaction() as connection:
            self._authorized_project(connection, principal, project_id, Permission.ADMINISTER)
            storage_refs = tuple(
                str(row[0])
                for row in connection.execute(
                    "SELECT storage_ref FROM artifacts WHERE project_id=? "
                    "AND storage_ref IS NOT NULL",
                    (project_id,),
                ).fetchall()
            )
            sample_refs = tuple(
                str(row[0])
                for row in connection.execute(
                    "SELECT object_ref FROM source_samples WHERE project_id=?",
                    (project_id,),
                ).fetchall()
            )
            self._audit(
                connection, principal.user_id, project_id, "project.delete", "project", project_id
            )
            connection.execute(
                "UPDATE projects SET name='Deleted project', deleted_at=?, updated_by=?, "
                "updated_at=?, specification_confirmed=0 WHERE project_id=?",
                (timestamp, principal.user_id, timestamp, project_id),
            )
            for table in ("validation_results", "job_results", "artifacts", "jobs"):
                connection.execute(f"DELETE FROM {table} WHERE project_id=?", (project_id,))
            for table in (
                "requirement_proposals",
                "confirmed_schemas",
                "source_samples",
                "specification_revisions",
                "source_configs",
                "project_members",
            ):
                connection.execute(f"DELETE FROM {table} WHERE project_id=?", (project_id,))
        return storage_refs, sample_refs

    def add_member(self, principal: Principal, project_id: str, user_id: str, role: Role) -> None:
        if role is Role.OWNER:
            raise PermissionDenied("Ownership transfer is not supported by this operation.")
        timestamp = _now()
        with self.database.transaction() as connection:
            self._authorized_project(connection, principal, project_id, Permission.ADMINISTER)
            user = connection.execute(
                "SELECT 1 FROM users WHERE user_id=? AND active=1", (user_id,)
            ).fetchone()
            if user is None:
                raise ResourceNotFound("User was not found.")
            connection.execute(
                "INSERT INTO project_members(project_id, user_id, role, created_by, created_at) "
                "VALUES (?, ?, ?, ?, ?) ON CONFLICT(project_id, user_id) DO UPDATE SET "
                "role=excluded.role, created_by=excluded.created_by, "
                "created_at=excluded.created_at",
                (project_id, user_id, role, principal.user_id, timestamp),
            )
            self._audit(
                connection,
                principal.user_id,
                project_id,
                "member.update",
                "user",
                user_id,
                {"role": role},
            )

    def transition_project(
        self, principal: Principal, project_id: str, target: ProjectStatus
    ) -> ProjectView:
        with self.database.transaction() as connection:
            row = self._authorized_project(connection, principal, project_id, Permission.EDIT)
            current = str(row["status"])
            if target not in _ALLOWED_TRANSITIONS.get(current, frozenset()):
                raise InvalidStateTransition(
                    f"Cannot transition project from {current} to {target}."
                )
            self._set_project_state(connection, project_id, target, principal.user_id)
            self._audit(
                connection,
                principal.user_id,
                project_id,
                "project.transition",
                "project",
                project_id,
                {"from": current, "to": target},
            )
        return self.get_project(principal, project_id)

    def save_source_config(
        self, principal: Principal, project_id: str, kind: str, config: dict[str, Any]
    ) -> int:
        self._reject_secrets(config)
        timestamp = _now()
        with self.database.transaction() as connection:
            row = self._authorized_project(connection, principal, project_id, Permission.EDIT)
            revision = int(row["current_revision"]) + 1
            source_id = str(uuid4())
            connection.execute(
                "INSERT INTO source_configs(source_config_id, project_id, revision, kind, "
                "config_json, created_by, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    source_id,
                    project_id,
                    revision,
                    kind,
                    json.dumps(config, sort_keys=True, separators=(",", ":")),
                    principal.user_id,
                    timestamp,
                ),
            )
            connection.execute(
                "UPDATE projects SET current_revision=?, status=?, specification_confirmed=0, "
                "record_version=record_version+1, updated_by=?, updated_at=? WHERE project_id=?",
                (
                    revision,
                    ProjectStatus.SOURCE_READY,
                    principal.user_id,
                    timestamp,
                    project_id,
                ),
            )
            self._audit(
                connection,
                principal.user_id,
                project_id,
                "upload",
                "source_config",
                source_id,
                {"revision": revision, "kind": kind},
            )
        return revision

    def save_ingested_file(
        self,
        principal: Principal,
        project_id: str,
        config: dict[str, Any],
        storage_ref: str,
        expires_at: datetime,
    ) -> tuple[int, str]:
        """Atomically persist file metadata and its temporary object reference."""

        self._reject_secrets(config)
        timestamp = _now()
        source_id = str(uuid4())
        sample_id = str(uuid4())
        with self.database.transaction() as connection:
            row = self._authorized_project(connection, principal, project_id, Permission.EDIT)
            revision = int(row["current_revision"]) + 1
            connection.execute(
                "INSERT INTO source_configs(source_config_id, project_id, revision, kind, "
                "config_json, created_by, created_at) VALUES (?, ?, ?, 'file', ?, ?, ?)",
                (
                    source_id,
                    project_id,
                    revision,
                    json.dumps(config, sort_keys=True, separators=(",", ":")),
                    principal.user_id,
                    timestamp,
                ),
            )
            connection.execute(
                "INSERT INTO source_samples(sample_id, project_id, revision, object_ref, "
                "expires_at, created_by, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    sample_id,
                    project_id,
                    revision,
                    storage_ref,
                    expires_at.astimezone(UTC).isoformat(),
                    principal.user_id,
                    timestamp,
                ),
            )
            connection.execute(
                "UPDATE projects SET current_revision=?, status=?, specification_confirmed=0, "
                "record_version=record_version+1, updated_by=?, updated_at=? WHERE project_id=?",
                (
                    revision,
                    ProjectStatus.SOURCE_READY,
                    principal.user_id,
                    timestamp,
                    project_id,
                ),
            )
            self._audit(
                connection,
                principal.user_id,
                project_id,
                "upload",
                "source_config",
                source_id,
                {"revision": revision, "format": config.get("file_format")},
            )
        return revision, sample_id

    def get_latest_source_config(self, principal: Principal, project_id: str) -> dict[str, Any]:
        project = self.get_project(principal, project_id)
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT kind, config_json, revision FROM source_configs "
                "WHERE project_id=? AND revision=?",
                (project_id, project.current_revision),
            ).fetchone()
        if row is None:
            raise ResourceNotFound("Source configuration was not found.")
        return {
            "kind": str(row["kind"]),
            "revision": int(row["revision"]),
            "config": json.loads(str(row["config_json"])),
        }

    def get_schema(self, principal: Principal, project_id: str) -> dict[str, Any]:
        source = self.get_latest_source_config(principal, project_id)
        profile = source["config"].get("profile")
        if not isinstance(profile, dict):
            raise ResourceNotFound("An inferred schema was not found for the current source.")
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT schema_json, schema_fingerprint, confirmed_by, confirmed_at "
                "FROM confirmed_schemas WHERE project_id=? AND revision=?",
                (project_id, source["revision"]),
            ).fetchone()
        confirmed = None
        if row is not None:
            confirmed = {
                "fields": json.loads(str(row["schema_json"])),
                "schema_fingerprint": str(row["schema_fingerprint"]),
                "confirmed_by": str(row["confirmed_by"]),
                "confirmed_at": str(row["confirmed_at"]),
            }
        return {
            "revision": source["revision"],
            "inferred": profile,
            "confirmed": confirmed,
        }

    def confirm_schema(
        self,
        principal: Principal,
        project_id: str,
        confirmation: SchemaConfirmation,
    ) -> dict[str, Any]:
        source = self.get_latest_source_config(principal, project_id)
        self.get_project(principal, project_id, Permission.EDIT)
        profile = source["config"].get("profile")
        if not isinstance(profile, dict) or not isinstance(profile.get("fields"), list):
            raise ResourceNotFound("An inferred schema was not found for the current source.")
        inferred = {field["name"]: field for field in profile["fields"]}
        if {field.name for field in confirmation.fields} != set(inferred):
            raise RevisionConflict("Confirmed fields must match the current inferred schema.")
        normalized: list[ConfirmedField] = []
        for field in confirmation.fields:
            source_field = inferred[field.name]
            if field.inferred_type.value != source_field["inferred_type"]:
                raise RevisionConflict("The inferred schema changed before confirmation.")
            pii_classification = field.pii_classification
            if source_field["pii_classification"] != "none" and pii_classification.value == "none":
                pii_classification = PiiClassification(source_field["pii_classification"])
            normalized.append(
                field.model_copy(
                    update={
                        "nullable": bool(source_field["nullable"]),
                        "required": bool(source_field["required"]),
                        "confidence": float(source_field["confidence"]),
                        "null_percentage": float(source_field["null_percentage"]),
                        "distinct_count": int(source_field["distinct_count"]),
                        "samples_masked": tuple(source_field["samples_masked"]),
                        "pii_classification": pii_classification,
                    }
                )
            )
        serialized = [field.model_dump(mode="json") for field in normalized]
        encoded = json.dumps(serialized, sort_keys=True, separators=(",", ":"))
        fingerprint = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        confirmed_at = _now()
        with self.database.transaction() as connection:
            self._authorized_project(connection, principal, project_id, Permission.EDIT)
            try:
                connection.execute(
                    "INSERT INTO confirmed_schemas(project_id, revision, schema_json, "
                    "schema_fingerprint, confirmed_by, confirmed_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        project_id,
                        source["revision"],
                        encoded,
                        fingerprint,
                        principal.user_id,
                        confirmed_at,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise RevisionConflict(
                    "The schema for this revision is already confirmed."
                ) from exc
            connection.execute(
                "UPDATE projects SET status=?, specification_confirmed=0, "
                "record_version=record_version+1, updated_by=?, updated_at=? WHERE project_id=?",
                (
                    ProjectStatus.AWAITING_CONFIRMATION,
                    principal.user_id,
                    confirmed_at,
                    project_id,
                ),
            )
            self._audit(
                connection,
                principal.user_id,
                project_id,
                "schema.confirm",
                "confirmed_schema",
                project_id,
                {"revision": source["revision"], "schema_fingerprint": fingerprint},
            )
        return {
            "revision": source["revision"],
            "schema_fingerprint": fingerprint,
            "confirmed_at": confirmed_at,
        }

    def get_confirmed_schema(
        self, principal: Principal, project_id: str, permission: Permission = Permission.VIEW
    ) -> ConfirmedSchema:
        project = self.get_project(principal, project_id, permission)
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT schema_json, schema_fingerprint, confirmed_by, confirmed_at "
                "FROM confirmed_schemas WHERE project_id=? AND revision=?",
                (project_id, project.current_revision),
            ).fetchone()
        if row is None:
            raise ResourceNotFound("A confirmed schema was not found for the current revision.")
        return ConfirmedSchema(
            project_id=project_id,
            revision=project.current_revision,
            fields=tuple(
                ConfirmedField.model_validate(field)
                for field in json.loads(str(row["schema_json"]))
            ),
            schema_fingerprint=str(row["schema_fingerprint"]),
            confirmed_by=str(row["confirmed_by"]),
            confirmed_at=datetime.fromisoformat(str(row["confirmed_at"])),
        )

    def save_requirement_proposal(
        self,
        principal: Principal,
        project_id: str,
        requirement: dict[str, Any],
        analysis: dict[str, Any],
        model_name: str,
    ) -> str:
        project = self.get_project(principal, project_id, Permission.EDIT)
        self.get_confirmed_schema(principal, project_id, Permission.EDIT)
        proposal_id = str(uuid4())
        with self.database.transaction() as connection:
            self._authorized_project(connection, principal, project_id, Permission.EDIT)
            connection.execute(
                "INSERT INTO requirement_proposals(proposal_id, project_id, revision, "
                "requirement_json, analysis_json, model_name, created_by, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    proposal_id,
                    project_id,
                    project.current_revision,
                    json.dumps(requirement, sort_keys=True, separators=(",", ":")),
                    json.dumps(analysis, sort_keys=True, separators=(",", ":")),
                    model_name,
                    principal.user_id,
                    _now(),
                ),
            )
            self._audit(
                connection,
                principal.user_id,
                project_id,
                "requirement.propose",
                "requirement_proposal",
                proposal_id,
                {"revision": project.current_revision, "model": model_name},
            )
        return proposal_id

    def get_requirement_proposal(
        self, principal: Principal, project_id: str, proposal_id: str
    ) -> dict[str, Any]:
        project = self.get_project(principal, project_id)
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT revision, requirement_json, analysis_json, model_name, created_at "
                "FROM requirement_proposals WHERE proposal_id=? AND project_id=?",
                (proposal_id, project_id),
            ).fetchone()
        if row is None or int(row["revision"]) != project.current_revision:
            raise ResourceNotFound("Requirement proposal was not found for the current revision.")
        return {
            "proposal_id": proposal_id,
            "revision": int(row["revision"]),
            "requirement": json.loads(str(row["requirement_json"])),
            "analysis": json.loads(str(row["analysis_json"])),
            "model": str(row["model_name"]),
            "created_at": str(row["created_at"]),
        }

    def confirm_specification(
        self, principal: Principal, project_id: str, specification: PipelineSpecification
    ) -> str:
        if str(specification.project_id) != project_id:
            raise RevisionConflict("Specification project does not match the target project.")
        spec_fingerprint = model_fingerprint(specification)
        schema_fingerprint = hashlib.sha256(
            json.dumps(
                [field.model_dump(mode="json") for field in specification.fields],
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        with self.database.transaction() as connection:
            row = self._authorized_project(connection, principal, project_id, Permission.EDIT)
            if int(row["current_revision"]) != specification.revision:
                raise RevisionConflict("Specification revision is stale.")
            try:
                connection.execute(
                    "INSERT INTO specification_revisions(project_id, revision, specification_json, "
                    "specification_fingerprint, source_fingerprint, schema_fingerprint, "
                    "confirmed_by, confirmed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        project_id,
                        specification.revision,
                        specification.model_dump_json(),
                        spec_fingerprint,
                        specification.source_fingerprint,
                        schema_fingerprint,
                        principal.user_id,
                        _now(),
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise RevisionConflict("A specification already exists for this revision.") from exc
            self._set_project_state(
                connection, project_id, ProjectStatus.CONFIRMED, principal.user_id, confirmed=True
            )
            self._audit(
                connection,
                principal.user_id,
                project_id,
                "confirm",
                "specification",
                str(specification.specification_id),
                {"revision": specification.revision, "fingerprint": spec_fingerprint},
            )
        return spec_fingerprint

    def list_specification_versions(
        self, principal: Principal, project_id: str
    ) -> tuple[PipelineSpecification, ...]:
        self.get_project(principal, project_id)
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT specification_json FROM specification_revisions WHERE project_id=? "
                "ORDER BY revision DESC",
                (project_id,),
            ).fetchall()
        return tuple(PipelineSpecification.model_validate_json(row[0]) for row in rows)

    def get_current_specification(
        self, principal: Principal, project_id: str, permission: Permission = Permission.VIEW
    ) -> PipelineSpecification:
        """Return only the confirmed specification for the project's current revision."""

        project = self.get_project(principal, project_id, permission)
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT specification_json FROM specification_revisions "
                "WHERE project_id=? AND revision=?",
                (project_id, project.current_revision),
            ).fetchone()
        if row is None:
            raise InvalidStateTransition("A confirmed specification is required.")
        return PipelineSpecification.model_validate_json(row[0])

    def submit_job(
        self,
        principal: Principal,
        project_id: str,
        operation: str,
        idempotency_key: str,
        *,
        generator_version: str,
        model_version: str | None = None,
        max_attempts: int = 3,
    ) -> tuple[JobView, bool]:
        timestamp = _now()
        with self.database.transaction() as connection:
            project = self._authorized_project(connection, principal, project_id, Permission.EDIT)
            revision = int(project["current_revision"])
            existing = connection.execute(
                "SELECT * FROM jobs WHERE project_id=? AND revision=? AND operation=? "
                "AND idempotency_key=?",
                (project_id, revision, operation, idempotency_key),
            ).fetchone()
            if existing is not None:
                return self._job_view(existing), False
            if not bool(project["specification_confirmed"]):
                raise InvalidStateTransition("A confirmed specification is required.")
            active_count = int(
                connection.execute(
                    "SELECT COUNT(*) FROM jobs WHERE status IN (?, ?, ?)",
                    (JobStatus.QUEUED, JobStatus.RUNNING, JobStatus.CANCELLING),
                ).fetchone()[0]
            )
            if active_count >= self.queue_capacity:
                raise CapacityLimit("The local job queue is full.")
            identity = connection.execute(
                "SELECT source_fingerprint, schema_fingerprint, specification_fingerprint "
                "FROM specification_revisions WHERE project_id=? AND revision=?",
                (project_id, revision),
            ).fetchone()
            if identity is None:
                raise InvalidStateTransition("Confirmed revision identity was not found.")
            job_id = str(uuid4())
            connection.execute(
                "INSERT INTO jobs(job_id, project_id, revision, operation, idempotency_key, "
                "status, max_attempts, source_fingerprint, schema_fingerprint, "
                "specification_fingerprint, generator_version, model_version, created_by, "
                "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    job_id,
                    project_id,
                    revision,
                    operation,
                    idempotency_key,
                    JobStatus.QUEUED,
                    max_attempts,
                    str(identity["source_fingerprint"]),
                    str(identity["schema_fingerprint"]),
                    str(identity["specification_fingerprint"]),
                    generator_version,
                    model_version,
                    principal.user_id,
                    timestamp,
                    timestamp,
                ),
            )
            self._audit(
                connection,
                principal.user_id,
                project_id,
                "generate",
                "job",
                job_id,
                {"revision": revision, "operation": operation},
            )
            row = connection.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
            assert row is not None
            return self._job_view(row), True

    def get_job(self, principal: Principal, project_id: str, job_id: str) -> JobView:
        self.get_project(principal, project_id)
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM jobs WHERE job_id=? AND project_id=?", (job_id, project_id)
            ).fetchone()
        if row is None:
            raise ResourceNotFound("Job was not found.")
        return self._job_view(row)

    def cancel_job(self, principal: Principal, project_id: str, job_id: str) -> JobView:
        timestamp = _now()
        with self.database.transaction() as connection:
            self._authorized_project(connection, principal, project_id, Permission.EDIT)
            row = connection.execute(
                "SELECT * FROM jobs WHERE job_id=? AND project_id=?", (job_id, project_id)
            ).fetchone()
            if row is None:
                raise ResourceNotFound("Job was not found.")
            status = str(row["status"])
            if status == JobStatus.QUEUED:
                new_status = JobStatus.CANCELLED
                completed_at = timestamp
            elif status == JobStatus.RUNNING:
                new_status = JobStatus.CANCELLING
                completed_at = None
            else:
                return self._job_view(row)
            connection.execute(
                "UPDATE jobs SET status=?, cancellation_requested=1, updated_at=?, "
                "completed_at=? WHERE job_id=?",
                (new_status, timestamp, completed_at, job_id),
            )
            self._audit(connection, principal.user_id, project_id, "job.cancel", "job", job_id)
            updated = connection.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
            assert updated is not None
            return self._job_view(updated)

    def claim_next_job(self, worker_id: str, *, concurrency_limit: int = 1) -> JobView | None:
        timestamp = _now()
        with self.database.transaction() as connection:
            running = int(
                connection.execute(
                    "SELECT COUNT(*) FROM jobs WHERE status IN (?, ?)",
                    (JobStatus.RUNNING, JobStatus.CANCELLING),
                ).fetchone()[0]
            )
            if running >= concurrency_limit:
                return None
            row = connection.execute(
                "SELECT * FROM jobs WHERE status=? ORDER BY created_at LIMIT 1",
                (JobStatus.QUEUED,),
            ).fetchone()
            if row is None:
                return None
            connection.execute(
                "UPDATE jobs SET status=?, attempt=attempt+1, worker_id=?, started_at=?, "
                "updated_at=? WHERE job_id=?",
                (JobStatus.RUNNING, worker_id, timestamp, timestamp, str(row["job_id"])),
            )
            updated = connection.execute(
                "SELECT * FROM jobs WHERE job_id=?", (str(row["job_id"]),)
            ).fetchone()
            assert updated is not None
            return self._job_view(updated)

    def claim_job(self, job_id: str, worker_id: str) -> JobView:
        """Claim one known queued job for a synchronous UI/API export."""

        timestamp = _now()
        with self.database.transaction() as connection:
            row = connection.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
            if row is None:
                raise ResourceNotFound("Job was not found.")
            if str(row["status"]) != JobStatus.QUEUED:
                raise InvalidStateTransition("Only a queued job can be claimed.")
            connection.execute(
                "UPDATE jobs SET status=?, attempt=attempt+1, worker_id=?, started_at=?, "
                "updated_at=? WHERE job_id=?",
                (JobStatus.RUNNING, worker_id, timestamp, timestamp, job_id),
            )
            updated = connection.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
            assert updated is not None
            return self._job_view(updated)

    def report_progress(self, job_id: str, percentage: int) -> None:
        if not 0 <= percentage <= 99:
            raise ValueError("running job progress must be between 0 and 99")
        with self.database.transaction() as connection:
            row = connection.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
            if row is None:
                raise ResourceNotFound("Job was not found.")
            if str(row["status"]) != JobStatus.RUNNING:
                raise InvalidStateTransition("Only a running job can report progress.")
            if percentage < int(row["progress_percentage"]):
                raise InvalidStateTransition("Job progress cannot move backwards.")
            connection.execute(
                "UPDATE jobs SET progress_percentage=?, updated_at=? WHERE job_id=?",
                (percentage, _now(), job_id),
            )

    def complete_job(
        self,
        job_id: str,
        result: dict[str, Any],
        validation_result: dict[str, Any],
        *,
        validation_passed: bool,
    ) -> JobView:
        timestamp = _now()
        with self.database.transaction() as connection:
            job = connection.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
            if job is None:
                raise ResourceNotFound("Job was not found.")
            if str(job["status"]) not in {JobStatus.RUNNING, JobStatus.CANCELLING}:
                raise InvalidStateTransition("Only an active job can complete.")
            if bool(job["cancellation_requested"]):
                final_status = JobStatus.CANCELLED
                error_code = "CANCELLED_BY_USER"
            elif not self._job_revision_is_current(connection, job):
                final_status = JobStatus.FAILED
                error_code = "STALE_REVISION"
            elif not validation_passed:
                final_status = JobStatus.FAILED
                error_code = "VALIDATION_FAILED"
            else:
                final_status = JobStatus.SUCCEEDED
                error_code = None
                connection.execute(
                    "INSERT INTO job_results(job_id, project_id, revision, result_json, "
                    "created_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (
                        job_id,
                        str(job["project_id"]),
                        int(job["revision"]),
                        json.dumps(result, sort_keys=True),
                        timestamp,
                    ),
                )
                connection.execute(
                    "INSERT INTO artifacts(artifact_id, job_id, project_id, revision, "
                    "source_fingerprint, schema_fingerprint, specification_fingerprint, "
                    "manifest_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        str(uuid4()),
                        job_id,
                        str(job["project_id"]),
                        int(job["revision"]),
                        str(job["source_fingerprint"]),
                        str(job["schema_fingerprint"]),
                        str(job["specification_fingerprint"]),
                        json.dumps(result, sort_keys=True),
                        timestamp,
                    ),
                )
            connection.execute(
                "INSERT INTO validation_results(validation_result_id, job_id, project_id, "
                "revision, passed, result_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    str(uuid4()),
                    job_id,
                    str(job["project_id"]),
                    int(job["revision"]),
                    int(validation_passed),
                    json.dumps(validation_result, sort_keys=True),
                    timestamp,
                ),
            )
            connection.execute(
                "UPDATE jobs SET status=?, progress_percentage=?, completed_at=?, updated_at=?, "
                "error_code=? WHERE job_id=?",
                (
                    final_status,
                    100 if final_status == JobStatus.SUCCEEDED else int(job["progress_percentage"]),
                    timestamp,
                    timestamp,
                    error_code,
                    job_id,
                ),
            )
            updated = connection.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
            assert updated is not None
            return self._job_view(updated)

    def fail_job(self, job_id: str, error_code: str, *, retryable: bool) -> JobView:
        with self.database.transaction() as connection:
            job = connection.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
            if job is None:
                raise ResourceNotFound("Job was not found.")
            if str(job["status"]) != JobStatus.RUNNING:
                raise InvalidStateTransition("Only a running job can fail.")
            should_retry = retryable and int(job["attempt"]) < int(job["max_attempts"])
            status = JobStatus.QUEUED if should_retry else JobStatus.FAILED
            completed_at = None if should_retry else _now()
            connection.execute(
                "UPDATE jobs SET status=?, worker_id=NULL, updated_at=?, completed_at=?, "
                "error_code=? WHERE job_id=?",
                (status, _now(), completed_at, error_code, job_id),
            )
            updated = connection.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
            assert updated is not None
            return self._job_view(updated)

    def recover_interrupted_jobs(self) -> tuple[int, int]:
        recovered = 0
        failed = 0
        with self.database.transaction() as connection:
            rows = connection.execute(
                "SELECT * FROM jobs WHERE status IN (?, ?)",
                (JobStatus.RUNNING, JobStatus.CANCELLING),
            ).fetchall()
            for row in rows:
                if bool(row["cancellation_requested"]):
                    status = JobStatus.CANCELLED
                    completed_at = _now()
                    failed += 1
                elif int(row["attempt"]) < int(row["max_attempts"]):
                    status = JobStatus.QUEUED
                    completed_at = None
                    recovered += 1
                else:
                    status = JobStatus.FAILED
                    completed_at = _now()
                    failed += 1
                connection.execute(
                    "UPDATE jobs SET status=?, worker_id=NULL, completed_at=?, updated_at=?, "
                    "error_code='WORKER_INTERRUPTED' WHERE job_id=?",
                    (status, completed_at, _now(), str(row["job_id"])),
                )
                connection.execute("DELETE FROM job_results WHERE job_id=?", (str(row["job_id"]),))
        return recovered, failed

    def operational_status(self) -> dict[str, int]:
        """Return non-sensitive queue gauges for readiness and monitoring."""

        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT status, COUNT(*) AS count FROM jobs GROUP BY status"
            ).fetchall()
            connection.execute("SELECT 1").fetchone()
        counts = {str(row["status"]): int(row["count"]) for row in rows}
        return {
            "queued": counts.get(JobStatus.QUEUED, 0),
            "running": counts.get(JobStatus.RUNNING, 0),
            "failed": counts.get(JobStatus.FAILED, 0),
        }

    def list_audit_events(
        self, principal: Principal, project_id: str
    ) -> tuple[dict[str, Any], ...]:
        self.get_project(principal, project_id, Permission.ADMINISTER)
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT event_id, actor_id, action, resource_type, resource_id, metadata_json, "
                "created_at FROM audit_events WHERE project_id=? ORDER BY created_at",
                (project_id,),
            ).fetchall()
        return tuple(
            {
                "event_id": str(row["event_id"]),
                "actor_id": str(row["actor_id"]),
                "action": str(row["action"]),
                "resource_type": str(row["resource_type"]),
                "resource_id": str(row["resource_id"]) if row["resource_id"] else None,
                "metadata": json.loads(str(row["metadata_json"])),
                "created_at": str(row["created_at"]),
            }
            for row in rows
        )

    def register_sample_reference(
        self,
        principal: Principal,
        project_id: str,
        object_ref: str,
        expires_at: datetime,
    ) -> str:
        """Store only a temporary object reference, never sample row content."""

        sample_id = str(uuid4())
        with self.database.transaction() as connection:
            project = self._authorized_project(connection, principal, project_id, Permission.EDIT)
            connection.execute(
                "INSERT INTO source_samples(sample_id, project_id, revision, object_ref, "
                "expires_at, created_by, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    sample_id,
                    project_id,
                    int(project["current_revision"]),
                    object_ref,
                    expires_at.astimezone(UTC).isoformat(),
                    principal.user_id,
                    _now(),
                ),
            )
        return sample_id

    def get_sample_reference(self, principal: Principal, project_id: str, sample_id: str) -> str:
        self.get_project(principal, project_id)
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT object_ref FROM source_samples WHERE sample_id=? AND project_id=? "
                "AND expires_at>?",
                (sample_id, project_id, _now()),
            ).fetchone()
        if row is None:
            raise ResourceNotFound("Sample was not found.")
        return str(row["object_ref"])

    def get_job_validation(
        self, principal: Principal, project_id: str, job_id: str
    ) -> dict[str, Any]:
        self.get_job(principal, project_id, job_id)
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT passed, result_json FROM validation_results WHERE job_id=? "
                "ORDER BY created_at DESC LIMIT 1",
                (job_id,),
            ).fetchone()
        if row is None:
            raise ResourceNotFound("Validation result was not found.")
        return {"passed": bool(row["passed"]), "result": json.loads(str(row["result_json"]))}

    def get_artifact_manifest(
        self, principal: Principal, project_id: str, artifact_id: str
    ) -> dict[str, Any]:
        project = self.get_project(principal, project_id)
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT job_id, revision, manifest_json, source_fingerprint, schema_fingerprint, "
                "specification_fingerprint, storage_ref, artifact_status, package_checksum "
                "FROM artifacts WHERE artifact_id=? AND project_id=?",
                (artifact_id, project_id),
            ).fetchone()
        if row is None:
            raise ResourceNotFound("Artifact was not found.")
        revision = int(row["revision"])
        return {
            "artifact_id": artifact_id,
            "job_id": str(row["job_id"]),
            "revision": revision,
            "current_revision": project.current_revision,
            "stale": revision != project.current_revision,
            "historical": revision != project.current_revision,
            "source_fingerprint": str(row["source_fingerprint"]),
            "schema_fingerprint": str(row["schema_fingerprint"]),
            "specification_fingerprint": str(row["specification_fingerprint"]),
            "artifact_status": str(row["artifact_status"]),
            "package_checksum": (str(row["package_checksum"]) if row["package_checksum"] else None),
            "download_available": bool(row["storage_ref"]),
            "manifest": json.loads(str(row["manifest_json"])),
        }

    def list_artifacts(self, principal: Principal, project_id: str) -> tuple[dict[str, Any], ...]:
        self.get_project(principal, project_id)
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT artifact_id FROM artifacts WHERE project_id=? ORDER BY created_at DESC",
                (project_id,),
            ).fetchall()
        return tuple(
            self.get_artifact_manifest(principal, project_id, str(row["artifact_id"]))
            for row in rows
        )

    def get_artifact_for_job(
        self, principal: Principal, project_id: str, job_id: str
    ) -> dict[str, Any]:
        self.get_job(principal, project_id, job_id)
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT artifact_id FROM artifacts WHERE project_id=? AND job_id=?",
                (project_id, job_id),
            ).fetchone()
        if row is None:
            raise ResourceNotFound("Artifact was not found.")
        return self.get_artifact_manifest(principal, project_id, str(row["artifact_id"]))

    def attach_artifact_package(
        self,
        principal: Principal,
        project_id: str,
        artifact_id: str,
        *,
        storage_ref: str,
        artifact_status: str,
        package_checksum: str,
        manifest: dict[str, Any],
    ) -> dict[str, Any]:
        with self.database.transaction() as connection:
            self._authorized_project(connection, principal, project_id, Permission.EDIT)
            updated = connection.execute(
                "UPDATE artifacts SET storage_ref=?, artifact_status=?, package_checksum=?, "
                "manifest_json=? WHERE artifact_id=? AND project_id=?",
                (
                    storage_ref,
                    artifact_status,
                    package_checksum,
                    json.dumps(manifest, sort_keys=True),
                    artifact_id,
                    project_id,
                ),
            )
            if updated.rowcount != 1:
                raise ResourceNotFound("Artifact was not found.")
        return self.get_artifact_manifest(principal, project_id, artifact_id)

    def get_artifact_storage_ref(
        self, principal: Principal, project_id: str, artifact_id: str
    ) -> str:
        self.get_project(principal, project_id)
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT storage_ref FROM artifacts WHERE artifact_id=? AND project_id=?",
                (artifact_id, project_id),
            ).fetchone()
        if row is None or not row["storage_ref"]:
            raise ResourceNotFound("Artifact package was not found.")
        return str(row["storage_ref"])

    def authorize_artifact_download(
        self, principal: Principal, project_id: str, artifact_id: str
    ) -> dict[str, Any]:
        manifest = self.get_artifact_manifest(principal, project_id, artifact_id)
        with self.database.transaction() as connection:
            self._authorized_project(connection, principal, project_id, Permission.VIEW)
            self._audit(
                connection,
                principal.user_id,
                project_id,
                "download",
                "artifact",
                artifact_id,
            )
        return manifest

    def record_audit_event(
        self,
        principal: Principal,
        project_id: str,
        action: str,
        resource_type: str,
        resource_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Append an authorized event for workflow actions owned by later phases."""

        with self.database.transaction() as connection:
            self._authorized_project(connection, principal, project_id, Permission.EDIT)
            self._audit(
                connection,
                principal.user_id,
                project_id,
                action,
                resource_type,
                resource_id,
                metadata,
            )

    @staticmethod
    def _reject_secrets(value: object, path: tuple[str, ...] = ()) -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                normalized = key.lower().replace("-", "_")
                key_parts = set(normalized.split("_"))
                if normalized in _FORBIDDEN_SECRET_KEYS or key_parts & {
                    "password",
                    "secret",
                    "token",
                }:
                    location = ".".join((*path, key))
                    raise SecretValueRejected(
                        "Source configuration must use a secret reference, not secret material.",
                        details={"field": location},
                    )
                Repository._reject_secrets(nested, (*path, key))
        elif isinstance(value, list):
            for index, nested in enumerate(value):
                Repository._reject_secrets(nested, (*path, str(index)))
        elif isinstance(value, str) and "://" in value:
            parsed = urlsplit(value)
            if parsed.password is not None:
                raise SecretValueRejected(
                    "Connection URLs containing credentials are not allowed; use connection_ref.",
                    details={"field": ".".join(path)},
                )

    @staticmethod
    def _project_view(row: sqlite3.Row) -> ProjectView:
        return ProjectView(
            project_id=str(row["project_id"]),
            owner_id=str(row["owner_id"]),
            name=str(row["name"]),
            status=str(row["status"]),
            current_revision=int(row["current_revision"]),
            record_version=int(row["record_version"]),
            specification_confirmed=bool(row["specification_confirmed"]),
            created_by=str(row["created_by"]),
            updated_by=str(row["updated_by"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    @staticmethod
    def _job_view(row: sqlite3.Row) -> JobView:
        return JobView(
            job_id=str(row["job_id"]),
            project_id=str(row["project_id"]),
            revision=int(row["revision"]),
            operation=str(row["operation"]),
            status=str(row["status"]),
            progress_percentage=int(row["progress_percentage"]),
            attempt=int(row["attempt"]),
            max_attempts=int(row["max_attempts"]),
            cancellation_requested=bool(row["cancellation_requested"]),
            error_code=str(row["error_code"]) if row["error_code"] else None,
        )

    @staticmethod
    def _authorized_project(
        connection: sqlite3.Connection,
        principal: Principal,
        project_id: str,
        required: Permission,
    ) -> sqlite3.Row:
        row = cast(
            sqlite3.Row | None,
            connection.execute(
                "SELECT p.*, m.role FROM projects p JOIN project_members m "
                "ON m.project_id=p.project_id WHERE p.project_id=? AND m.user_id=? "
                "AND p.deleted_at IS NULL",
                (project_id, principal.user_id),
            ).fetchone(),
        )
        if row is None:
            raise ResourceNotFound("Project was not found.")
        role = Role(str(row["role"]))
        if ROLE_PERMISSION[role] < required:
            raise PermissionDenied("The current role cannot perform this action.")
        return row

    @staticmethod
    def _set_project_state(
        connection: sqlite3.Connection,
        project_id: str,
        status: ProjectStatus,
        actor_id: str,
        *,
        confirmed: bool | None = None,
    ) -> None:
        if confirmed is None:
            connection.execute(
                "UPDATE projects SET status=?, record_version=record_version+1, updated_by=?, "
                "updated_at=? WHERE project_id=?",
                (status, actor_id, _now(), project_id),
            )
        else:
            connection.execute(
                "UPDATE projects SET status=?, specification_confirmed=?, "
                "record_version=record_version+1, updated_by=?, updated_at=? WHERE project_id=?",
                (status, int(confirmed), actor_id, _now(), project_id),
            )

    @staticmethod
    def _audit(
        connection: sqlite3.Connection,
        actor_id: str,
        project_id: str | None,
        action: str,
        resource_type: str,
        resource_id: str | None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        connection.execute(
            "INSERT INTO audit_events(event_id, actor_id, project_id, action, resource_type, "
            "resource_id, metadata_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                str(uuid4()),
                actor_id,
                project_id,
                action,
                resource_type,
                resource_id,
                json.dumps(metadata or {}, sort_keys=True),
                _now(),
            ),
        )

    @staticmethod
    def _job_revision_is_current(connection: sqlite3.Connection, job: sqlite3.Row) -> bool:
        row = connection.execute(
            "SELECT p.current_revision, p.specification_confirmed, "
            "s.source_fingerprint, s.schema_fingerprint, s.specification_fingerprint "
            "FROM projects p LEFT JOIN specification_revisions s ON s.project_id=p.project_id "
            "AND s.revision=p.current_revision WHERE p.project_id=?",
            (str(job["project_id"]),),
        ).fetchone()
        return bool(
            row
            and int(row["current_revision"]) == int(job["revision"])
            and bool(row["specification_confirmed"])
            and str(row["source_fingerprint"]) == str(job["source_fingerprint"])
            and str(row["schema_fingerprint"]) == str(job["schema_fingerprint"])
            and str(row["specification_fingerprint"]) == str(job["specification_fingerprint"])
        )
