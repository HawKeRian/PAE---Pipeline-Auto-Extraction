# Developer Guide

PAE uses Python 3.11 in conda environment `ai_env`. Install from `requirements.txt`, copy the
non-secret `.env.example`, and run `uvicorn pae.main:app --app-dir src`.

The canonical flow is API/UI → ingestion/profiling → confirmed schema → Local Llama proposal →
confirmed immutable Specification → shared preview runtime → language generator → validation → ZIP.
Every persistence method authorizes its project boundary. Source samples are temporary files;
SQLite stores opaque references only. Add behavior to the shared `runtime_core` before adding a
generator-specific rendering so parity remains testable.

Quality commands:

```text
python -m ruff check src tests scripts
python -m ruff format --check src tests scripts
python -m mypy src/pae
python -m pytest
detect-secrets scan src/pae
pip-audit -r requirements.txt
```

When adding a source, update the strict domain contract, capability/scope matrices, connector
network/secret policy, ingestion limits, generated runtime, docs, shared fixtures, adversarial tests,
and traceability. Database integration tests require explicitly configured disposable services and
remain skipped otherwise. Never put real samples, tokens, model output containing source values, or
`.env` files in Git.

Migrations append to `MIGRATIONS`; never rewrite an applied migration. Generated artifacts and
revisions are immutable. Use an idempotency key for job/export submission, and fail closed when a
job revision is no longer current.
