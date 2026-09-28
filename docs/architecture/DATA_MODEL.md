# Persistence Model

## Logical Tables

| Table | Key fields | Notes |
|---|---|---|
| users | user_id | Identity reference; no external password design in Phase 2 |
| projects | project_id, owner_id, status, current_revision | Ownership boundary |
| project_members | project_id, user_id, role | Future collaboration-ready |
| source_configs | source_config_id, project_id, revision, kind, config_json | Secret references only |
| source_samples | sample_id, project_id, source_fingerprint, expires_at | Encrypted temporary object reference |
| schema_revisions | project_id, revision, schema_json, fingerprint | Immutable |
| specification_revisions | project_id, revision, specification_json, fingerprint | Immutable confirmed intent |
| jobs | job_id, project_id, revision, idempotency_key, status | Unique idempotency tuple |
| job_attempts | job_id, attempt, lease, timestamps, error_code | Recovery evidence |
| artifacts | artifact_id, project_id, revision, manifest_json | Immutable, authorized download |
| audit_events | event_id, actor_id, project_id, action, timestamp | Append-only |

## Constraints

- Every project-owned row includes `project_id` for authorization filtering.
- Revision rows are insert-only.
- Artifact and job foreign keys include project/revision association.
- Secret values are never stored in JSON configuration columns.
- Sample object references expire and deletion is audited.
- Database migrations must support clean install, upgrade and failure recovery tests.
