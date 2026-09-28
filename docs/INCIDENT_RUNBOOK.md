# Incident Runbook

1. Confirm `/health`, `/ready`, metrics, image version, queue depth, model status, disk, and recent
   redacted JSON errors. Never paste tokens/source rows into an incident channel.
2. Stop new submissions if correctness, authorization, deletion, or artifact integrity is at risk.
3. For model failure, keep confirmed specs/artifacts accessible and restore Ollama/model readiness.
4. For stuck workers, stop the instance and restart; persisted running jobs are recovered according
   to retry/cancellation limits. Do not manually edit revision identities.
5. For storage/database corruption, stop writes, preserve evidence, restore a verified encrypted
   backup into empty volumes, run integrity/readiness/smoke checks, then resume.
6. For a release regression, follow the immutable-image rollback procedure in the operations guide.
7. Record timeline, affected projects, safe metadata, root cause, recovery time, and follow-up tests.

## Alert Delivery Check

1. Temporarily set the queue threshold below the observed test queue depth in a non-production
   verification window.
2. Call `/ready`; require `alert_delivery=delivered` and confirm one message at the on-call receiver.
3. Call `/ready` again; require `alert_delivery=throttled` during the cooldown.
4. Confirm `pae_alert_delivery_total` contains both results, then restore the approved threshold.
5. Record receiver, operator, timestamp, and incident/ticket reference without copying webhook URLs.
