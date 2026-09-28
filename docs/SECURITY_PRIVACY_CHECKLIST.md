# Security and Privacy Release Checklist

Status: Approved for the local MVP implementation review on 2026-09-27.

- [x] Upload type, signature, archive expansion, path, size, row, and column controls tested.
- [x] Database secret references, TLS, host egress, read-only query, timeout, and bounds tested.
- [x] Local Llama receives no source rows/credentials; output requires schema validation and confirmation.
- [x] Validation sandbox workspace, process/network, time, memory, and output restrictions tested.
- [x] Source and artifact secret scans plus dependency audit are quality gates.
- [x] Project resources, samples, versions, jobs, artifacts, and downloads enforce membership.
- [x] Logout revokes the token and role changes apply on the next request.
- [x] Rate limiting, queue/upload limits, and security headers are enabled by default.
- [x] PII is masked in profiles, previews, and sample output; errors do not echo input values.
- [x] Deletion purges samples, specs, jobs, validation data, and ZIPs; audit tombstone is anonymized.
- [x] Production HSTS is enabled; TLS termination and encrypted storage are deployment requirements.

No open Critical or High application issue was identified. Phase 17 must verify reverse-proxy TLS,
encrypted host storage, service-account permissions, multi-replica shared rate limiting, encrypted
backups, and deletion propagation.

Repeatable evidence: run Ruff, mypy, pytest, detect-secrets, and `pip-audit -r requirements.txt` in
`ai_env`. Tests are in `tests/test_ingestion.py`, `tests/test_connectors.py`, `tests/test_ai.py`,
`tests/test_preview_generation.py`, `tests/test_persistence.py`, `tests/test_api.py`, and
`tests/test_ui.py`.
