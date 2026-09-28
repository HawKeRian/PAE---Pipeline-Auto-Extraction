# Deployment and Operations Guide

## Podman deployment

1. Copy `configs/production.env.example` to ignored `configs/production.env` and set a generated
   bootstrap token. Keep model/database secrets outside the image.
2. Confirm Ollama exposes the selected Llama model to the container and leave
   `PAE_READINESS_REQUIRE_MODEL=true` for production.
3. Run `podman compose -f deploy/compose.yaml up --build -d`.
4. Require `/health` and `/ready` HTTP 200, then run `python scripts/smoke_test.py`.
5. Terminate TLS at the approved reverse proxy; expose the container only on loopback. Enable host
   volume encryption and back up both named volumes.

The image runs as a non-root user, drops Linux capabilities, applies no-new-privileges, uses a
read-only root filesystem, and writes only to data/generated volumes plus bounded tmpfs workspaces.

## Monitoring and alerts

Collect JSON logs from stdout and scrape `/metrics`. Alert on readiness failure, HTTP 5xx/rate,
queue depth, failed jobs, latency, process memory, disk capacity, backup age, and model availability.
`/ready` emits `job_queue_depth_high` when the configured queue threshold is reached. Do not attach
request bodies, tokens, source rows, or database details to alerts.

Set `PAE_ALERT_WEBHOOK_URL` to an operator-owned HTTPS receiver. Delivery is bounded by
`PAE_ALERT_WEBHOOK_TIMEOUT_SECONDS` and duplicate alert sets are throttled by
`PAE_ALERT_WEBHOOK_COOLDOWN_SECONDS`. `/ready` reports `alert_delivery` as `delivered`, `failed`,
`throttled`, or `disabled`; `/metrics` exposes `pae_alert_delivery_total`. Before public release,
trigger a queue-depth alert in the target environment and record receipt by the real on-call route.

## Upgrade and rollback

Back up first. Build an immutable version tag, run migrations and smoke checks in a separate
environment, then switch traffic. Roll back by stopping the new image, restoring the pre-upgrade
backup into empty volumes, and starting the previous immutable image. Never run an older binary
against a database after a newer migration without a verified compatible restore.

Recovery targets for local MVP: RPO 24 hours, RTO 4 hours. The service owner is incident commander;
the data owner approves restores/deletion exceptions. See `BACKUP_RECOVERY.md`.
