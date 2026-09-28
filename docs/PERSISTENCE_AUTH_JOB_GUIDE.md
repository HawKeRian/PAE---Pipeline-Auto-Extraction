# Persistence, Authentication, and Job Foundation

สถานะ: **Phase 4 baseline — 2026-09-27**

## Local persistence

PAE uses SQLite from the Python standard library. The default file is `data/pae.sqlite3`, which
is excluded from Git. Set `PAE_DATABASE_PATH` to use another local path. Migrations run in
versioned transactions and support clean installation, incremental upgrade, and rollback when
a migration fails.

The current schema stores users, projects, memberships, immutable source configurations,
immutable Pipeline Specification revisions, jobs, validation results, job results, temporary
sample object references, artifact manifests, and append-only audit events. Database triggers
reject updates/deletes of confirmed specification and source configuration history.

## Authentication and roles

Set a high-entropy token only in the local `.env` file:

```text
PAE_BOOTSTRAP_USER_ID=local-admin
PAE_BOOTSTRAP_USER_NAME=Local Administrator
PAE_BOOTSTRAP_TOKEN=<random value with at least 16 characters>
```

Use `Authorization: Bearer <token>` for `/api/v1` requests. Only a SHA-256 digest is persisted;
the token is not logged or returned. This is an MVP local authentication mechanism, not an
internet-facing identity provider.

| Role | Read project resources | Edit project/source/spec/jobs | Manage members/delete/audit |
|---|---:|---:|---:|
| owner | yes | yes | yes |
| editor | yes | yes | no |
| viewer | yes | no | no |

Unauthorized project lookups return the same not-found response as missing resources, preventing
cross-user existence disclosure. Samples, jobs, versions, validation results, artifacts, and
download authorization all pass through the project membership boundary.

## Revision and secret rules

- Source changes create a new project revision, invalidate the current confirmation, and return
  the project to `source_ready`.
- Confirmation inserts an immutable specification revision with source, schema, and specification
  fingerprints.
- A stale revision or duplicate confirmation is rejected rather than overwritten.
- Source configuration accepts a secret-managed `connection_ref`; keys such as password, token,
  API key, client secret, and connection URI are rejected recursively.
- Connection URLs containing embedded passwords are rejected even under an unrelated key.
- Sample storage contains only an expiring encrypted/object-store reference, never row content.

## Jobs and recovery

Jobs are persisted before execution and uniquely keyed by project, revision, operation, and
idempotency key. Duplicate submissions return the original job. Queue capacity, worker
concurrency, monotonic progress, cooperative cancellation, and bounded attempts are enforced.

`JobWorker.run_once` claims one queued job. Retryable failures return it to the queue until the
attempt limit; terminal failures stop immediately. Startup/recovery code can call
`recover_interrupted_jobs()` to requeue eligible interrupted jobs, fail exhausted jobs, cancel
requested work, and remove partial job-result rows.

Successful completion verifies that the project revision and all three fingerprints still match
before committing the result and artifact manifest. If source/schema/specification changed while
a worker was running, the job ends with `STALE_REVISION`; old output cannot overwrite the current
revision. Only one local AI inference should run at a time on the reference machine.

## Audit and error contract

Audit events are append-only and include actor, project, action, resource, timestamp, and bounded
metadata. The workflow supports `upload`, `analyze`, `confirm`, `generate`, `execute`, and
`download` events plus project/member/job lifecycle actions.

Expected API failures use the standard envelope with stable code, safe message, details,
request ID, and retryable flag. Validation errors omit the submitted input value, and internal
exceptions, credentials, and source samples are never included.
