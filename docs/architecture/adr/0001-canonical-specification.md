# ADR-0001: Pydantic Pipeline Specification Is Canonical

Status: Accepted — 2026-09-26

## Decision

Use strict, frozen Pydantic models as the executable Pipeline Specification and export JSON Schema from those models.

## Consequences

- API, persistence, AI validation, preview and generators share one contract.
- Unknown fields fail closed.
- Schema generation is reproducible.
- Major semantic changes require a specification-version migration.
