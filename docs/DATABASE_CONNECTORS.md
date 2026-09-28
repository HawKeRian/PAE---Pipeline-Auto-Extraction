# Database Source Connectors

Phase 6 provides read-only source discovery and bounded sampling for PostgreSQL, MySQL, and
Microsoft SQL Server. Database destinations and write operations remain outside the MVP.

## API workflow

All endpoints require project edit permission:

```text
POST /api/v1/projects/{project_id}/database-sources/test
POST /api/v1/projects/{project_id}/database-sources/catalog
POST /api/v1/projects/{project_id}/database-sources/analyze
```

`test` checks connectivity and verifies that the session/account can be used read-only.
`catalog` returns schemas, tables, and views. `analyze` accepts either a selected object or one
custom SELECT query, fetches a bounded sample, and saves only the source configuration and column
names. Sample rows and credentials are not written into the project source configuration.

## Connection and secret configuration

The request contains non-secret connection fields: database type, host, port, database name,
username, TLS mode, and a reference such as `secret://warehouse/read-only`. It must never contain
a password, token, connection URI, or DSN with embedded credentials.

The built-in local resolver maps that reference to an environment variable:

```text
secret://warehouse/read-only -> PAE_SECRET_WAREHOUSE_READ_ONLY
```

The password is resolved only while opening a connection. It is represented with `SecretStr`, is
not persisted, and is excluded from API results and errors. API responses also mask host,
database, username, and the secret-reference name.

## Network and TLS policy

Set an exact, comma-separated host allowlist before enabling database access:

```text
PAE_DATABASE_ALLOWED_HOSTS=db.example.com,warehouse.example.com
PAE_DATABASE_ALLOW_PRIVATE_HOSTS=false
```

When an allowlist is present, other hosts are rejected. Private, loopback, link-local, multicast,
and reserved addresses are rejected unless both the exact hostname is allowlisted and
`PAE_DATABASE_ALLOW_PRIVATE_HOSTS=true`. DNS results are inspected before connecting.

TLS defaults to identity verification. Supported modes are:

- `verify_identity`: encryption, certificate-chain validation, and hostname validation;
- `verify_ca`: encryption and certificate-chain validation;
- `require`: encryption without identity validation, intended only for controlled development.

PostgreSQL uses its native SSL modes, MySQL uses a Python TLS context, and SQL Server uses ODBC
Driver 18 with `Encrypt=yes` and `ApplicationIntent=ReadOnly`.

## Read-only and query safety

Custom SQL is parsed as one statement using the correct database dialect. Only query ASTs are
accepted. Mutations, DDL, SELECT INTO, locking SELECTs, multiple statements, and selected unsafe
functions are rejected before connecting.

This parser is not the sole control. PostgreSQL uses `BEGIN READ ONLY`; MySQL uses
`START TRANSACTION READ ONLY`; SQL Server requires a read-only account, uses
`ApplicationIntent=ReadOnly`, and rejects accounts with effective database mutation permissions.
Every operation is rolled back and the connection is closed. Timeout or caller cancellation also
cancels the active driver operation and performs cleanup.

Samples are wrapped in a connector-generated outer SELECT that requests at most `limit + 1` rows
to detect truncation. Configure global bounds with:

```text
PAE_DATABASE_QUERY_TIMEOUT_SECONDS=30
PAE_DATABASE_SAMPLE_ROWS=10000
```

## Test-database integration

Phase acceptance does not require a production or externally managed database. A disposable
PostgreSQL test container on Podman is the reference integration environment; MySQL and SQL Server
use the same connector contract suite and may be enabled as additional test containers when
needed. The default quality gate skips container integration unless a test database is explicitly
configured. For PostgreSQL, set:

```text
PAE_TEST_POSTGRESQL_HOST=
PAE_TEST_POSTGRESQL_PORT=5432
PAE_TEST_POSTGRESQL_DATABASE=
PAE_TEST_POSTGRESQL_USER=
PAE_TEST_POSTGRESQL_PASSWORD=
PAE_TEST_POSTGRESQL_TLS_MODE=require
```

Equivalent prefixes are `PAE_TEST_MYSQL_` and `PAE_TEST_SQL_SERVER_`. The accounts must be
dedicated read-only test accounts. Run:

```powershell
conda run -n ai_env pytest -m integration tests/test_database_integration.py
```

The integration test verifies TLS connection, bounded SELECT sampling, credential exclusion, and
that a direct mutation attempt fails at the database/session permission layer. Use disposable test
credentials only. The test container and any temporary certificate should be removed after the
run.
