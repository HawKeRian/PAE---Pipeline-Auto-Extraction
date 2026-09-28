# Output Contract

## MVP Destinations

Generated output is an artifact file or SQL result contract. Direct writes to destination databases are deferred.

| Format | Encoding | Null representation | MVP write mode |
|---|---|---|---|
| CSV | UTF-8 | Configured string, default empty | Overwrite/append |
| JSON Lines | UTF-8 | JSON `null` | Overwrite/append |
| Parquet | Typed binary | Native null | Overwrite/append where supported |
| SQL result | Database driver | Dialect-native | Read-only result contract |

## Atomicity

- Overwrite writes to a revision-scoped temporary path first.
- The final path is replaced only after validation and close succeed.
- Failed/cancelled jobs delete partial temporary output.
- Append uses a job/idempotency marker and must not duplicate data on bounded retry.
- Artifact manifests are written last and indicate completion.

## Repeated Runs

- Same revision plus same idempotency key returns the existing effective job/result.
- A new explicit run may create a new artifact ID but retains the same revision identity.
- Output from an old revision cannot replace the current revision's artifact pointer.
- File-batch generators track stable file identity using configured manifest/checksum or archive policy.
- A file is marked processed only after its output and manifest commit successfully.
- Failed or quarantined files are not recorded as successfully processed.

## Schema

The output schema is derived from selected `FieldDefinition.target_name` and confirmed type after transformation/aggregation. Generators must fail if they cannot preserve the confirmed type semantics.
