# ADR-0004: Confirmed Revisions and Artifacts Are Immutable

Status: Accepted — 2026-09-26

## Decision

Bind jobs and artifacts to source, schema and specification fingerprints plus generator/model versions. Changes create new revisions rather than mutating confirmed history.

## Consequences

- Stale results can be detected and labeled.
- Old workers cannot overwrite current revision pointers.
- Historical artifacts remain reproducible and auditable.
- Storage and cleanup policies must account for versioned history.
