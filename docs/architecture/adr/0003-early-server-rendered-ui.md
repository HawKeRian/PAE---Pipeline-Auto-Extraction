# ADR-0003: Early UI Uses Server-rendered Jinja2

Status: Accepted — 2026-09-26

## Decision

Use Jinja2 and minimal vanilla JavaScript for the Early Test UI. Introduce HTMX or a separate frontend only when real interaction complexity justifies it.

## Consequences

- Python remains the primary toolchain.
- Usability can be tested before backend completion.
- Mock routes are gated to development/testing and forbidden in production.
