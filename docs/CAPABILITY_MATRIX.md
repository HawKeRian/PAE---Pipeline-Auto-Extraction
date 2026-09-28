# MVP Capability Matrix

`Supported` means a generator must implement shared semantics and pass parity fixtures. `Reject` means validation must stop before generation.

| Capability | Python | PostgreSQL | MySQL | SQL Server | JavaScript |
|---|---|---|---|---|---|
| Include/Exclude/Rename | Supported | Supported | Supported | Supported | Supported |
| Cast | Supported | Supported | Supported | Supported | Supported |
| Filter/Sort | Supported | Supported | Supported | Supported | Supported |
| Null handling/Replace | Supported | Supported | Supported | Supported | Supported |
| Deduplicate | Supported | Supported | Supported | Supported | Supported |
| Derived field | Supported | Supported | Supported | Supported | Supported |
| Aggregate | Supported | Supported | Supported | Supported | Supported |
| Validation/rejected rows | Supported | Query contract | Query contract | Query contract | Supported |
| Sensitive masking | Supported | Supported | Supported | Supported | Supported |
| Multi-source Join | Reject (Deferred) | Reject (Deferred) | Reject (Deferred) | Reject (Deferred) | Reject (Deferred) |
| CSV output | Supported | Reject | Reject | Reject | Supported |
| JSON Lines output | Supported | Reject | Reject | Reject | Supported |
| Parquet output | Supported | Reject | Reject | Reject | Reject |
| SQL result contract | Reject | Supported | Supported | Supported | Reject |
| Folder batch discovery | Supported | Reject | Reject | Reject | Supported |
| Processed-file manifest | Supported | Reject | Reject | Reject | Supported |
| Quarantine policy | Supported | Reject | Reject | Reject | Supported |

The executable declarations live in `src/pae/domain/capabilities.py`. Documentation and code must change together.
