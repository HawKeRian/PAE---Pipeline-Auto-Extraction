# Shared Transformation Semantics

Preview and every generator must implement these semantics or reject the rule before generation.

## Rule Ordering

- Rules execute by unique positive `order`.
- Include/exclude selection is resolved before value transformations.
- Rename changes the canonical target reference for subsequent rules.
- Validation runs after transformations unless a rule explicitly targets source input validation.
- Aggregation runs after row-level filter/cast/null handling.

## Nulls

- Empty string is not automatically null unless configured by a null-handling rule.
- Null comparisons use `is null`/`is not null` semantics, never equality.
- Aggregates ignore null values except count-all.
- A non-nullable output with null invokes the selected `ErrorPolicy`.

## Decimal

- Decimal values use base-10 decimal semantics, not binary floating point.
- Precision and scale must be declared when the target requires them.
- Overflow and invalid separators reject the record or fail the job according to policy.
- Rounding mode must be explicit; default is no implicit rounding.

## Date, Time and Timezone

- Date parsing uses an ordered allowlist of formats.
- Ambiguous values such as `01/02/2026` require a confirmed locale/format.
- Datetime output uses ISO 8601.
- Naive datetime values require a confirmed source timezone.
- Conversion to another timezone happens only through an explicit rule.

## Locale and Text

- String comparison is case-sensitive unless configured otherwise.
- Trim and Unicode normalization are explicit transformations.
- Thousands and decimal separators are explicit parameters.
- Encoding is part of source/output contracts.

## Sorting and Deduplication

- Sort is stable.
- Null ordering must be declared for generators where behavior differs.
- Deduplication requires keys and a deterministic survivor rule.
- If no survivor order is defined, the request is rejected rather than relying on engine order.

## Masking

- Masking happens before values are shown in UI/logs/rejected previews.
- Generated pipelines use confirmed masking rules independently of UI masking.
- Raw values must not be embedded in specification or artifacts.

## Joins

- Join source aliases, join type, keys and expected cardinality are required.
- Key arity must match.
- Duplicate column handling is explicit: prefix or reject.
- Null keys never match unless an explicit future semantic is approved.
- Multi-source joins are deferred from MVP and therefore fail capability validation.
