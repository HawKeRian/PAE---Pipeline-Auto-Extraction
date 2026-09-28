# Transformation Preview and Python Generation

## Preview contract

`POST /api/v1/projects/{project_id}/preview` accepts bounded sample rows only after the project has
a confirmed specification. It returns masked before/after rows, input/output/rejected counts,
per-rule impact, and separate validation errors and warnings. Missing required columns return a
`SCHEMA_CHANGED` response with the affected rule IDs.

Preview execution runs in a new disposable workspace for each request. The worker has a sanitized
environment, no network or child-process access, and cannot open files outside that workspace.
The parent process enforces wall-clock, CPU, memory, and output-size limits, kills the process tree
on cancellation or failure, and removes the workspace in every exit path. Limits are configured by
the `PAE_SANDBOX_*` environment settings.

## Shared semantics

`src/pae/runtime_core.py` is the single deterministic implementation for Preview and generated
Python. It implements every MVP transformation and validation. The generator copies this file
verbatim; shared expected-output fixtures verify include/exclude, rename, cast, filter, sort,
deduplicate, replacement, null handling, derive, aggregate, masking, and all validation kinds.
Multi-source Join remains Deferred and is rejected before execution or generation.

## Generated package

The Python generator produces:

- `pipeline.py` with file/database readers, schema checking, logging, output writers, and the batch CLI;
- `runtime_core.py` with the same transformation semantics as Preview;
- `pipeline_spec.json`, `requirements.txt`, `config.example.env`, `README.md`, and a generated test;
- a deterministic package checksum.

The CLI requires `--input-dir`, `--output-dir`, `--quarantine-dir`, and `--state-file`. For file
sources it discovers the confirmed relative glob in deterministic path order, checks required and
extra columns, applies fail-batch/quarantine/skip policy, and records input SHA-256 values in an
atomically written manifest. Successful files are not processed again unless their content changes.
Inputs are copied—not moved—when quarantined.

CSV, JSON, JSON Lines, Excel, and Parquet readers are generated as needed. PostgreSQL, MySQL, and
SQL Server packages read connection configuration from the environment variable named by
`connection_ref`; credentials and machine-specific paths are rejected from generated artifacts.
CSV, JSON Lines, and Parquet outputs follow the confirmed overwrite/append and atomic-write contract.

Artifact validation stages are explicit: `generated`, `syntax_validated`, then `sample_tested` only
after the generated specification produces the same result as Preview inside the sandbox.
