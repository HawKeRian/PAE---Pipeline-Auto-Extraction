# API Contract Baseline

Base path: `/api/v1`

## Resources

| Method and path | Purpose |
|---|---|
| `POST /projects` | Create project |
| `GET /projects/{project_id}` | Read authorized project |
| `POST /projects/{project_id}/sources` | Register file/database source configuration |
| `POST /projects/{project_id}/analysis-jobs` | Queue bounded profiling job |
| `POST /projects/{project_id}/requirement-proposals` | Produce structured AI proposal |
| `GET /projects/{project_id}/schema` | Read inferred and current confirmed schema |
| `POST /projects/{project_id}/schema/confirm` | Confirm or override inferred field types |
| `POST /projects/{project_id}/profiles` | Profile a bounded connector sample |
| `GET /projects/{project_id}/requirement-proposals/{proposal_id}` | Read a version-bound proposal |
| `POST /projects/{project_id}/specification/confirm-from-proposal` | Validate edited rules/output and confirm an immutable specification |
| `PUT /projects/{project_id}/specification` | Validate and save draft specification |
| `POST /projects/{project_id}/specification/confirm` | Create immutable confirmed revision |
| `POST /projects/{project_id}/preview-jobs` | Queue preview for confirmed revision |
| `POST /projects/{project_id}/generation-jobs` | Queue generator job |
| `GET /projects/{project_id}/jobs/{job_id}` | Read status/progress |
| `POST /projects/{project_id}/jobs/{job_id}/cancel` | Request cancellation |
| `GET /projects/{project_id}/artifacts/{artifact_id}` | Read manifest |
| `GET /projects/{project_id}/artifacts/{artifact_id}/download` | Authorized package download |
| `GET /projects` | List projects visible to the authenticated user |
| `PATCH /projects/{project_id}` | Update project using `If-Match` optimistic locking |
| `DELETE /projects/{project_id}` | Soft-delete an owned project |
| `PUT /projects/{project_id}/members` | Assign editor/viewer role; owner only |
| `GET /projects/{project_id}/specification/versions` | Read immutable specification history |
| `GET /projects/{project_id}/jobs/{job_id}/validation` | Read authorized validation result |
| `GET /projects/{project_id}/audit-events` | Read append-only audit events; owner only |

## Error Envelope

```json
{
  "error": {
    "code": "SPECIFICATION_FIELD_UNKNOWN",
    "message": "A transformation references a field that is not selected.",
    "details": {"fields": ["missing_field"]},
    "request_id": "...",
    "retryable": false
  }
}
```

## Rules

- Resource authorization occurs before existence details are disclosed.
- Mutating job endpoints require idempotency keys.
- API returns revision and ETag; stale mutation uses `409 REVISION_CONFLICT`.
- Unsupported capability returns `422 CAPABILITY_UNSUPPORTED` before a job is queued.
- Queue saturation returns `429 CAPACITY_LIMIT` with retry guidance.
- Internal exception details, credentials and sample values are never returned.
- MVP authentication uses a local high-entropy bearer token; only its SHA-256 digest is stored.
- `owner`, `editor`, and `viewer` roles are checked against every project-owned resource.
- Artifact download currently authorizes and returns the immutable manifest; package streaming is
  added with generated artifacts in a later phase without changing the authorization boundary.
