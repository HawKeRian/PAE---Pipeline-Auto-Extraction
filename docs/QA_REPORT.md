# Phase 16 QA Report and Release Recommendation

Date: 2026-09-28. Environment: Windows, Python 3.11.16, conda `ai_env`.

Automated coverage includes all MVP file formats, connector drivers/policies, transformation and
validation fixtures, Python/JavaScript parity, all SQL dialects, Thai/English/mixed Local Llama
benchmark, malformed/adversarial uploads, sandbox escape/resource attempts, authorization,
concurrency/capacity/idempotency/recovery/cancellation, stale revisions, deletion, folder order,
schema compatibility, quarantine, atomic/repeat output, and clean generated-package execution.

Latest regression result: 180 passed, 3 opt-in disposable-database integration tests skipped in the
default suite, overall coverage 86.12% (threshold 80%). A separate disposable PostgreSQL 16 test
with TLS passed; MySQL and SQL Server remain covered by driver, policy, query and failure contract
tests without persistent external services. Core domain/spec/generator areas meet or exceed the
approved goal except shared runtime branch coverage, which is offset by complete rule fixture and
cross-generator parity evidence. No Critical/High defect is open.

Measured evidence in `reports/qa-benchmark-2026-09-27.json`:

| Workload | p95 | Threshold | Result |
|---|---:|---:|---|
| Profile 100,000 rows | 3.707 s | 60 s | Pass |
| Sandbox preview 10,000 rows | 0.310 s | 5 s | Pass |
| Python generation | 0.002 s | 60 s | Pass |
| Health endpoint | 0.008 s | 1 s | Pass |

The selected `llama3.1:8b` regression remains 100% schema-valid/semantic/safety on 10 cases, median
9.48 s and maximum 16.40 s. Dependency audit reports no known vulnerabilities and source secret
scan has zero findings.

Clean-environment evidence: wheel and sdist built successfully, Podman image
`localhost/pae:0.1.0-rc1` started as a non-root user, health/readiness/metrics smoke tests passed,
and an immutable-image restart using persistent volumes passed. Backup/restore integrity,
non-empty-target guards, HTTPS-only alert configuration, webhook delivery/failure and duplicate
cooldown pass in `tests/test_operations.py`. Artifact hashes and image identity are recorded in
`reports/release-0.1.0-rc1.json`.

Recommendation: **technical Go for a controlled pilot/release candidate; No-Go for public MVP until
real pilot completion and a production observation window are recorded.**
