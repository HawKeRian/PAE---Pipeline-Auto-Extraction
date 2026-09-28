# ADR-0002: Local Llama Behind an AI Provider Port

Status: Accepted — 2026-09-26

## Decision

Local Llama is the default AI implementation behind a provider interface. Model output is an untrusted proposal validated against the canonical specification schema.

## Consequences

- Runtime/model can change after benchmark without changing business logic.
- No model may directly confirm a specification.
- Hugging Face downloads require explicit need, license and hardware review.
