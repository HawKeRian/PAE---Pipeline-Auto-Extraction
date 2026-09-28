# Threat Model — Implementation Review

Last reviewed: 2026-09-27 (Phase 15)

## Protected Assets

- Source samples and inferred sensitive values
- Database connection references and resolved credentials
- Confirmed Pipeline Specifications
- Generated artifacts and validation evidence
- Local model files and prompts
- Project ownership and audit trail

## Threats and Required Controls

| Threat | Boundary | Required controls |
|---|---|---|
| Malicious upload/path traversal | Browser → File ingestion | Size/type/signature checks, random storage names, no archive extraction by default |
| Spreadsheet formula content | File → Preview/export | Treat cells as data, escape dangerous CSV output where applicable |
| Prompt injection in source values | Source → Local Llama | Separate data from instructions, bounded schema context, structured output validation |
| AI fabricates fields/rules | AI → Specification | Cross-reference validation, capability checks, user confirmation |
| SQL side effects | API → Connector | Read-only account/session, parser/policy, timeout, transaction rollback |
| SSRF/internal scanning | Connector network | Approved host/port allowlist, TLS verification, DNS/IP revalidation |
| Secret leakage | Config/log/artifact | Secret references, redaction, secret scanning, no raw connection URI |
| Cross-project access | API/storage | Project ownership on every resource and download URL |
| Stale job overwrites current result | Worker → Persistence | Immutable revision identity and compare-on-commit |
| Generated-code escape | Sandbox → Host | Separate identity, process/filesystem/network/resource isolation |
| Resource exhaustion | Upload/AI/sandbox | File/row limits, bounded queue, CPU/memory/time/process/output limits |
| Model/license risk | Model acquisition | Inventory, license review, checksum, trusted source, no automatic unreviewed download |

## Network Policies

- API may reach approved persistence and worker endpoints.
- Connectors reach only project-approved database endpoints.
- Local Llama runtime does not require outbound network.
- Validation sandbox has no network by default.
- Model download is an explicit administrative operation, never initiated from source content.

## Sandbox Boundaries

- Unique working directory per attempt.
- Non-privileged execution identity.
- Read-only generated code and sample input; dedicated writable output directory.
- CPU, memory, process count, wall time and output-size limits.
- No host environment secrets.
- Cleanup runs after all terminal outcomes and expired leases.

## Review Schedule

The Phase 15 review verified the implemented controls against file ingestion, database connectors,
Local Llama prompts, generated-code validation, project storage, and export downloads. Automated
tests cover unsafe filenames/archive expansion, read-only SQL, host/TLS policy, prompt/schema
separation, sandbox time/resource/path controls, cross-user denial, immediate role changes, logout,
stale revisions, retention, and complete project-data deletion.

## Implemented Defense Review

| Surface | Implemented evidence | Review result |
|---|---|---|
| Upload | Allowlisted types/signatures, safe random names, bounded XLSX expansion, row/column/byte limits | Pass |
| Database | `secret://` references, TLS-required config, host policy, read-only AST/session, timeout | Pass |
| Prompt/model | Only requirement plus confirmed names/types; strict output and user confirmation | Pass |
| Sandbox | Isolated workspace, minimal environment, CPU/memory/time/output bounds, Node permissions | Pass |
| Export | Bounded paths, deterministic ZIP, hashes, secret scan, authenticated download | Pass |
| Authorization | Membership on every resource; cross-user denial; immediate role changes | Pass |
| Abuse | Per-client/per-route rate limit plus queue/upload/model/sandbox bounds | Pass |
| Browser | CSP, frame denial, no-sniff, no-referrer, permissions policy, no-store, HSTS | Pass |
| Deletion | Samples/ZIPs removed; project rows purged; anonymized audit tombstone retained | Pass |

## Residual Risks and Deployment Requirements

- SQLite and artifact files rely on operating-system volume encryption. Production must enable
  BitLocker/LUKS (or equivalent) and restrict the service account. This is a medium operational
  dependency, not an unmitigated application Critical/High issue.
- TLS terminates at the approved reverse proxy. Production sets HSTS; direct HTTP remains bound to
  loopback or private service networking.
- Generated code is validated, not automatically promoted. Human production review and a target
  database test remain required.
- The in-memory rate limiter is process-local. A shared gateway limiter is required for multiple
  API replicas.

Review again after deployment topology changes, a new source/generator is introduced, or before
each release candidate.
