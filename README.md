# Pipeline Auto Extraction (PAE)

PAE generates validated data-pipeline code from source samples and a user-confirmed Pipeline Specification.

## Prerequisites

- Miniconda or Anaconda
- Conda environment name: `ai_env`
- Python 3.11

## Setup

Create the environment when it does not exist:

```powershell
conda env create -f environment.yml
```

If `ai_env` already exists, install Python and dependencies into that environment:

```powershell
conda install -n ai_env -c conda-forge python=3.11 pip
conda run -n ai_env python -m pip install -r requirements.txt
```

Copy `.env.example` to `.env` only for local settings. Never commit `.env` or secrets.

## Run

```powershell
conda run -n ai_env uvicorn pae.main:app --app-dir src --host 127.0.0.1 --port 8000
```

Open:

- `http://127.0.0.1:8000/ui` for the production API-backed workflow
- `http://127.0.0.1:8000/docs` for generated API documentation
- `http://127.0.0.1:8000/health` for the health endpoint
- `http://127.0.0.1:8000/ready` for persistence, storage, queue, and optional model readiness
- `http://127.0.0.1:8000/metrics` for Prometheus-compatible service metrics

Project APIs require a local bearer token. Generate a high-entropy token, store it only in
`.env` as `PAE_BOOTSTRAP_TOKEN`, and send it as `Authorization: Bearer <token>`. The application
stores only its SHA-256 digest in SQLite. The default database is `data/pae.sqlite3`; override
it with `PAE_DATABASE_PATH` when needed.

The production UI is available in every environment and uses the authenticated `/api/v1`
contracts. Prototype export routes are not registered. The browser keeps the token only in session
storage and logout revokes it server-side.

## Quality Checks

```powershell
conda run -n ai_env ruff check .
conda run -n ai_env ruff format --check .
conda run -n ai_env mypy
conda run -n ai_env pytest
conda run -n ai_env detect-secrets scan --all-files --exclude-files '^\.git/'
conda run -n ai_env pip-audit -r requirements.txt
```

Install local pre-commit hooks with:

```powershell
conda run -n ai_env pre-commit install
```

## Project Layout

```text
src/pae/        Application source
tests/          Automated tests
docs/           Product scope, decisions and traceability
configs/        Non-secret configuration templates
samples/        Synthetic/de-identified fixtures only
generated/      Local generated artifacts; ignored by Git
```

See `Progress.md` for the implementation plan and current status.

Project persistence, local authentication, RBAC, migrations, revision history, jobs, validation
results, artifacts, and audit events are documented in `docs/PERSISTENCE_AUTH_JOB_GUIDE.md`.

Secure file-source ingestion supports CSV, JSON, JSON Lines, XLSX, and Parquet. It profiles a
sample and suggests a reusable folder pattern plus required/optional columns without exposing raw
rows or hard-coding the sample path. See `docs/FILE_INGESTION_GUIDE.md` for the upload API,
configuration, limits, and retention behavior.

Read-only database discovery and bounded sampling are implemented for PostgreSQL, MySQL, and SQL
Server. Connection secrets are resolved by reference at runtime, with host/TLS policy and
AST-based SQL validation backed by read-only sessions. See `docs/DATABASE_CONNECTORS.md`.

Schema profiling, PII-safe sample display, confirmed-schema overrides, Local Llama requirement
proposals, editable rules, capability validation, and specification confirmation are documented
in `docs/PROFILING_AND_SPECIFICATION.md`.

Architecture contracts are documented under `docs/architecture/`. The executable Pipeline Specification is in `src/pae/domain/models.py`, with the generated JSON Schema under `schemas/`.

Generated file pipelines are designed as reusable scan-on-run packages: they discover matching future files in an input folder, validate schema compatibility, process each file deterministically, quarantine or reject incompatible files, and track completed files to prevent duplicate results. Continuous folder watching is intentionally delegated to an external scheduler for MVP.

Transformation Preview and standalone Python package generation now share one deterministic runtime
core. Preview uses a resource-bounded subprocess sandbox and masks sensitive values; generated
packages include a folder-batch CLI, manifest/checksum idempotency, schema failure policies, atomic
outputs, database environment references, README, requirements, and tests. See
`docs/PREVIEW_AND_PYTHON_GENERATION.md`.

Read-only SQL packages are generated for PostgreSQL, MySQL, and SQL Server with dialect-aware
quoting, separately bound parameters, validation queries, and explicit syntax/sample-test status.
Node.js packages provide the same shared transformation semantics, reusable folder processing,
database adapters, atomic outputs, and sandboxed parity validation. See
`docs/SQL_AND_JAVASCRIPT_GENERATION.md`.

Confirmed revisions can be downloaded as secret-scanned ZIP packages from the API or UI. Packages
include full reusable source, tests, README, configuration example, specification, masked sample
output, and artifact manifest. See `docs/EXPORT_PACKAGE_GUIDE.md` and
`docs/SECURITY_PRIVACY_CHECKLIST.md`.

## Local AI

Phase 3 uses `llama3.1:8b` through the local Ollama HTTP API. Start Ollama and make sure the
model is available before running AI-backed workflows:

```powershell
ollama pull llama3.1:8b
ollama list
conda run -n ai_env python scripts/benchmark_local_ai.py --model llama3.1:8b
```

Set `PAE_AI_MODEL`, `PAE_OLLAMA_BASE_URL`, and `PAE_AI_TIMEOUT_SECONDS` to change the local
runtime configuration. The application sends only the natural-language requirement and
confirmed field names/types to the model; source row values and credentials are excluded.
See `docs/MODEL_USAGE.md` and `docs/MODEL_EVALUATION.md` for operating and evaluation details.

## Container Deployment and Recovery

Build and run the release candidate with Podman:

```powershell
podman build -t localhost/pae:0.1.0 -f Containerfile .
podman compose -f deploy/compose.yaml up -d
conda run -n ai_env python scripts/smoke_test.py --base-url http://127.0.0.1:8000
```

Use `scripts/backup.py` and `scripts/restore.py` for application-state backups with SHA-256
manifest verification. Deployment, observability, alert thresholds, incident response, and
rollback steps are documented in `docs/DEPLOYMENT_OPERATIONS.md`, `docs/BACKUP_RECOVERY.md`, and
`docs/INCIDENT_RUNBOOK.md`.
