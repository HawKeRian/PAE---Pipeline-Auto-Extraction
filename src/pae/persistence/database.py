"""Transactional SQLite migrations and connection management."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path

MIGRATIONS: tuple[str, ...] = (
    """
    CREATE TABLE users (
        user_id TEXT PRIMARY KEY,
        display_name TEXT NOT NULL,
        token_hash TEXT NOT NULL UNIQUE,
        active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE TABLE projects (
        project_id TEXT PRIMARY KEY,
        owner_id TEXT NOT NULL REFERENCES users(user_id),
        name TEXT NOT NULL,
        status TEXT NOT NULL,
        current_revision INTEGER NOT NULL DEFAULT 0,
        record_version INTEGER NOT NULL DEFAULT 1,
        specification_confirmed INTEGER NOT NULL DEFAULT 0
            CHECK (specification_confirmed IN (0, 1)),
        created_by TEXT NOT NULL REFERENCES users(user_id),
        updated_by TEXT NOT NULL REFERENCES users(user_id),
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        deleted_at TEXT
    );
    CREATE TABLE project_members (
        project_id TEXT NOT NULL REFERENCES projects(project_id),
        user_id TEXT NOT NULL REFERENCES users(user_id),
        role TEXT NOT NULL CHECK (role IN ('owner', 'editor', 'viewer')),
        created_by TEXT NOT NULL REFERENCES users(user_id),
        created_at TEXT NOT NULL,
        PRIMARY KEY (project_id, user_id)
    );
    CREATE TABLE source_configs (
        source_config_id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL REFERENCES projects(project_id),
        revision INTEGER NOT NULL,
        kind TEXT NOT NULL,
        config_json TEXT NOT NULL,
        created_by TEXT NOT NULL REFERENCES users(user_id),
        created_at TEXT NOT NULL,
        UNIQUE (project_id, revision)
    );
    CREATE TABLE specification_revisions (
        project_id TEXT NOT NULL REFERENCES projects(project_id),
        revision INTEGER NOT NULL,
        specification_json TEXT NOT NULL,
        specification_fingerprint TEXT NOT NULL,
        source_fingerprint TEXT NOT NULL,
        schema_fingerprint TEXT NOT NULL,
        confirmed_by TEXT NOT NULL REFERENCES users(user_id),
        confirmed_at TEXT NOT NULL,
        PRIMARY KEY (project_id, revision)
    );
    CREATE TABLE jobs (
        job_id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL REFERENCES projects(project_id),
        revision INTEGER NOT NULL,
        operation TEXT NOT NULL,
        idempotency_key TEXT NOT NULL,
        status TEXT NOT NULL,
        progress_percentage INTEGER NOT NULL DEFAULT 0
            CHECK (progress_percentage BETWEEN 0 AND 100),
        attempt INTEGER NOT NULL DEFAULT 0,
        max_attempts INTEGER NOT NULL DEFAULT 3,
        cancellation_requested INTEGER NOT NULL DEFAULT 0 CHECK (cancellation_requested IN (0, 1)),
        worker_id TEXT,
        source_fingerprint TEXT NOT NULL,
        schema_fingerprint TEXT NOT NULL,
        specification_fingerprint TEXT NOT NULL,
        generator_version TEXT NOT NULL,
        model_version TEXT,
        created_by TEXT NOT NULL REFERENCES users(user_id),
        created_at TEXT NOT NULL,
        started_at TEXT,
        updated_at TEXT NOT NULL,
        completed_at TEXT,
        error_code TEXT,
        UNIQUE (project_id, revision, operation, idempotency_key)
    );
    CREATE TABLE audit_events (
        event_id TEXT PRIMARY KEY,
        actor_id TEXT NOT NULL REFERENCES users(user_id),
        project_id TEXT REFERENCES projects(project_id),
        action TEXT NOT NULL,
        resource_type TEXT NOT NULL,
        resource_id TEXT,
        metadata_json TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    CREATE INDEX idx_projects_owner ON projects(owner_id, deleted_at);
    CREATE INDEX idx_jobs_status ON jobs(status, created_at);
    CREATE INDEX idx_audit_project ON audit_events(project_id, created_at);
    """,
    """
    CREATE TABLE validation_results (
        validation_result_id TEXT PRIMARY KEY,
        job_id TEXT NOT NULL REFERENCES jobs(job_id),
        project_id TEXT NOT NULL REFERENCES projects(project_id),
        revision INTEGER NOT NULL,
        passed INTEGER NOT NULL CHECK (passed IN (0, 1)),
        result_json TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    CREATE TABLE job_results (
        job_id TEXT PRIMARY KEY REFERENCES jobs(job_id),
        project_id TEXT NOT NULL REFERENCES projects(project_id),
        revision INTEGER NOT NULL,
        result_json TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    CREATE TRIGGER specification_revisions_no_update
    BEFORE UPDATE ON specification_revisions
    BEGIN
        SELECT RAISE(ABORT, 'specification revisions are immutable');
    END;
    CREATE TRIGGER specification_revisions_no_delete
    BEFORE DELETE ON specification_revisions
    BEGIN
        SELECT RAISE(ABORT, 'specification revisions are immutable');
    END;
    CREATE TRIGGER source_configs_no_update
    BEFORE UPDATE ON source_configs
    BEGIN
        SELECT RAISE(ABORT, 'source configurations are immutable');
    END;
    CREATE TRIGGER source_configs_no_delete
    BEFORE DELETE ON source_configs
    BEGIN
        SELECT RAISE(ABORT, 'source configurations are immutable');
    END;
    """,
    """
    CREATE TABLE source_samples (
        sample_id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL REFERENCES projects(project_id),
        revision INTEGER NOT NULL,
        object_ref TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        created_by TEXT NOT NULL REFERENCES users(user_id),
        created_at TEXT NOT NULL
    );
    CREATE TABLE artifacts (
        artifact_id TEXT PRIMARY KEY,
        job_id TEXT NOT NULL UNIQUE REFERENCES jobs(job_id),
        project_id TEXT NOT NULL REFERENCES projects(project_id),
        revision INTEGER NOT NULL,
        source_fingerprint TEXT NOT NULL,
        schema_fingerprint TEXT NOT NULL,
        specification_fingerprint TEXT NOT NULL,
        manifest_json TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    CREATE INDEX idx_samples_project ON source_samples(project_id, expires_at);
    CREATE INDEX idx_artifacts_project ON artifacts(project_id, revision);
    """,
    """
    CREATE TABLE confirmed_schemas (
        project_id TEXT NOT NULL REFERENCES projects(project_id),
        revision INTEGER NOT NULL,
        schema_json TEXT NOT NULL,
        schema_fingerprint TEXT NOT NULL,
        confirmed_by TEXT NOT NULL REFERENCES users(user_id),
        confirmed_at TEXT NOT NULL,
        PRIMARY KEY (project_id, revision)
    );
    CREATE TABLE requirement_proposals (
        proposal_id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL REFERENCES projects(project_id),
        revision INTEGER NOT NULL,
        requirement_json TEXT NOT NULL,
        analysis_json TEXT NOT NULL,
        model_name TEXT NOT NULL,
        created_by TEXT NOT NULL REFERENCES users(user_id),
        created_at TEXT NOT NULL
    );
    CREATE INDEX idx_requirement_proposals_project
        ON requirement_proposals(project_id, revision, created_at);
    CREATE TRIGGER confirmed_schemas_no_update
    BEFORE UPDATE ON confirmed_schemas
    BEGIN
        SELECT RAISE(ABORT, 'confirmed schemas are immutable');
    END;
    CREATE TRIGGER confirmed_schemas_no_delete
    BEFORE DELETE ON confirmed_schemas
    BEGIN
        SELECT RAISE(ABORT, 'confirmed schemas are immutable');
    END;
    """,
    """
    ALTER TABLE artifacts ADD COLUMN storage_ref TEXT;
    ALTER TABLE artifacts ADD COLUMN artifact_status TEXT NOT NULL DEFAULT 'generated';
    ALTER TABLE artifacts ADD COLUMN package_checksum TEXT;

    DROP TRIGGER specification_revisions_no_delete;
    DROP TRIGGER source_configs_no_delete;
    DROP TRIGGER confirmed_schemas_no_delete;
    CREATE TRIGGER specification_revisions_no_delete
    BEFORE DELETE ON specification_revisions
    WHEN (SELECT deleted_at FROM projects WHERE project_id=OLD.project_id) IS NULL
    BEGIN
        SELECT RAISE(ABORT, 'specification revisions are immutable');
    END;
    CREATE TRIGGER source_configs_no_delete
    BEFORE DELETE ON source_configs
    WHEN (SELECT deleted_at FROM projects WHERE project_id=OLD.project_id) IS NULL
    BEGIN
        SELECT RAISE(ABORT, 'source configurations are immutable');
    END;
    CREATE TRIGGER confirmed_schemas_no_delete
    BEFORE DELETE ON confirmed_schemas
    WHEN (SELECT deleted_at FROM projects WHERE project_id=OLD.project_id) IS NULL
    BEGIN
        SELECT RAISE(ABORT, 'confirmed schemas are immutable');
    END;
    """,
)


class Database:
    """Own SQLite setup while exposing short, explicit transactions."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    def migrate(self, migrations: Sequence[str] = MIGRATIONS) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations "
                "(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
            )
            current = connection.execute(
                "SELECT COALESCE(MAX(version), 0) FROM schema_migrations"
            ).fetchone()[0]
            for version, sql in enumerate(migrations, start=1):
                if version <= current:
                    continue
                escaped_sql = sql.strip()
                script = (
                    "BEGIN IMMEDIATE;\n"
                    f"{escaped_sql}\n"
                    f"INSERT INTO schema_migrations(version) VALUES ({version});\n"
                    "COMMIT;"
                )
                try:
                    connection.executescript(script)
                except sqlite3.Error:
                    if connection.in_transaction:
                        connection.execute("ROLLBACK")
                    raise

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                yield connection
            except Exception:
                connection.rollback()
                raise
            else:
                connection.commit()
