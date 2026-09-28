# Profiling and Specification Workflow

Phases 7 and 8 turn a bounded source sample into a user-confirmed, immutable Pipeline
Specification. Inference and AI output are suggestions; neither can enter generation without
explicit user confirmation for the current source revision.

## Schema profiling

File upload and database sampling use the same deterministic `SchemaProfiler`. It reports:

- inferred type and all observed types, including mixed-type detection;
- detected date/datetime format;
- null count/percentage and distinct count;
- numeric or temporal minimum/maximum where appropriate;
- bounded sample values, masked before entering an API response;
- confidence, required/nullable status, and basic sensitive-data classification.

The profiler recognizes string, integer, decimal, boolean, date, datetime, JSON, and null/empty
observations. It processes no more than the configured sample bound and marks truncated results.
Thai field-name hints and Unicode values are supported.

Identifiers, email addresses, phone numbers, national IDs, card numbers, and IP addresses are
masked. Sensitive fields do not expose min/max. A user may override an inferred data type during
confirmation, but cannot replace masked samples or downgrade automatically detected PII to
`none`.

Relevant endpoints:

```text
GET  /api/v1/projects/{project_id}/schema
POST /api/v1/projects/{project_id}/schema/confirm
POST /api/v1/projects/{project_id}/profiles
```

The generic profile endpoint is intended for bounded connector samples. File/database ingestion
already profiles automatically. Confirmed schemas are immutable per project revision; a new
source creates a new revision and requires confirmation again.

## Requirement interpretation

```text
POST /api/v1/projects/{project_id}/requirement-proposals
GET  /api/v1/projects/{project_id}/requirement-proposals/{proposal_id}
```

The proposal endpoint accepts Thai, English, or mixed requirements. Only selected confirmed field
names and types are sent to the local Ollama provider. Raw rows, masked samples, credentials,
connection details, and source paths are excluded from the model request.

Ollama uses JSON Schema constrained output. Pydantic then validates the response, and the service
rejects unknown field references. Provider/schema/reference failures become a safe clarification
proposal with no rules. Proposals show status, confidence, assumptions, warnings, and
clarification questions and always have `requires_confirmation=true`.

## Editing and confirming rules

The client edits the complete `transformations` and `validations` arrays before confirmation. A
full-array replacement supports adding, editing, deleting, and reordering rules without allowing
partial stale updates. Transformation orders must be unique and consecutive.

```text
POST /api/v1/projects/{project_id}/specification/confirm-from-proposal
```

The confirmation request includes the edited rules, output contract, target language/dialect, and
explicit acknowledgement of assumptions/warnings. The server validates:

- every field reference against the current confirmed schema;
- transformation and output support against the target capability matrix;
- validation-rule fields and parameters against strict models;
- proposal readiness and current project revision;
- output format compatibility with Python, JavaScript, or the selected SQL dialect.

Include/exclude, rename, cast, filter, sort, deduplicate, replace, null handling, derive,
aggregate, validation, and masking are in MVP scope. Multi-source Join is explicitly deferred and
returns `UNSUPPORTED_CAPABILITY` rather than being guessed or partially generated.

Only the resulting confirmed specification is stored in immutable specification history. Job
submission checks `specification_confirmed` and refuses generation before confirmation.

## Local Llama verification

The Phase 8 regression uses `llama3.1:8b` with the 10-case Thai/English/mixed benchmark. The
2026-09-27 run passed schema validity, semantic correctness, and safety-critical checks at 100%.
The non-sensitive report is `reports/model-evaluation-phase8-llama3.1-8b.json`.
