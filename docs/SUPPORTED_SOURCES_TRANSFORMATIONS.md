# Supported Sources and Transformations

## MVP sources

| Source | Status | Notes |
|---|---|---|
| CSV, JSON, JSON Lines | Supported | Bounded sample; reusable folder batch runtime |
| XLSX | Supported | Safe ZIP inspection; bounded summaries of every Sheet, then explicit selection |
| Parquet | Supported | Bounded Arrow batches |
| PostgreSQL, MySQL, SQL Server | Supported | TLS/read-only/host policy; secrets by reference |

## Transformations and validations

Python and JavaScript support include/exclude, rename, cast, filter, sort, deduplicate, replace,
null handling, derive, aggregate, and mask through shared semantics. SQL support is dialect-specific
and is rejected before generation when a rule cannot be represented safely. Validations are
not-null, unique, range, regex where supported, and allowed-values. Advanced multi-source Join is
Deferred. See `CAPABILITY_MATRIX.md` for exact output and dialect combinations.

Python and JavaScript file packages support deterministic discovery, strict/allow-extra schema
policies, quarantine/fail/skip behavior, atomic output, overwrite/append where supported, and a
processed checksum manifest. SQL packages are read-only query contracts.
