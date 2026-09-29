# API Guide

Interactive OpenAPI is served at `/docs`; the machine-readable contract is `/openapi.json`. All
project endpoints use prefix `/api/v1` and require `Authorization: Bearer <token>`. Mutating job
submissions also require `Idempotency-Key`.

Main resources:

- `POST/GET /projects`, `GET/PATCH/DELETE /projects/{id}`
- `POST /projects/{id}/file-sources` and `/database-sources/*`
- `POST /projects/{id}/file-sources/{upload_id}/select-sheet` for a pending multi-sheet XLSX
- `GET /projects/{id}/schema`, `POST /schema/confirm`
- `POST /requirement-proposals`, `POST /specification/confirm-from-proposal`
- `GET /specification/versions`, `POST /preview`
- `POST /exports`, `GET /jobs/{job_id}`, `POST /jobs/{job_id}/cancel`
- `GET /artifacts`, `GET /artifacts/{artifact_id}/download`
- `POST /auth/logout`
- unauthenticated operations endpoints `/health`, `/ready`, `/metrics`

Errors use `{error: {code, message, details, request_id, retryable}}`. `404` is intentionally used
for resources outside the caller's project visibility. `409` indicates revision/confirmation/state
conflicts, `422` rejected input/capability, and `429` rate or queue capacity. API responses are
`no-store`; never log request bodies or authorization headers.

`/ready` returns dependency status, queue counts, active alert keys, and `alert_delivery`. When an
HTTPS webhook is configured, delivery results are `delivered`, `failed`, or `throttled`; otherwise
the result is `disabled`. `/metrics` includes request totals/duration, queue depth, process RSS, and
alert-delivery counters. Operations endpoints contain no credentials or source-row values.
