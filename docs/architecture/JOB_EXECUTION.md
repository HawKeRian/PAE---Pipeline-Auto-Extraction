# Job Execution Contract

## States

`queued → running → succeeded|failed|cancelling → cancelled`

Terminal states are immutable. A retry creates a new attempt record associated with the same logical job/idempotency key.

## Queue and Worker

- API persists the job before enqueueing.
- Queue capacity and per-project concurrency are bounded.
- Local Llama defaults to one active inference per available model runtime.
- Workers acquire a lease with heartbeat and expiry.
- Expired leases are recovered as retryable or failed according to error classification.

## Idempotency

- Client submits an idempotency key.
- `(project_id, revision, operation, idempotency_key)` is unique.
- Duplicate submission returns the existing logical job.
- Worker output uses a temporary artifact ID until commit.

## Retry Policy

- Validation/business errors are not retried.
- Transient infrastructure errors use bounded exponential backoff.
- Default maximum is three attempts.
- Retry never changes specification revision or silently upgrades generator/model version.

## Cancellation and Recovery

- Cancellation is cooperative first, then process termination after a grace period.
- Sandbox, temporary files and connector sessions are cleaned for success, failure, timeout, cancellation and crash recovery.
- Progress is monotonic within an attempt and never used as proof of completion.
- Only an artifact manifest and terminal success transaction establish completion.

## Backpressure

When queue capacity is reached, API returns a retryable capacity error rather than starting unbounded processes. Queue depth, oldest age, runtime and failures are observable metrics.
