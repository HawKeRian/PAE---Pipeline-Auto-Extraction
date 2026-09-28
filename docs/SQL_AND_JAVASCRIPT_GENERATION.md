# SQL and JavaScript Generation

## SQL boundary

The SQL generator accepts one confirmed database source and an `sql_result` output contract. File
sources and direct writes to source/destination tables are rejected. Multi-source Join remains
Deferred. A target dialect must match the confirmed source: PostgreSQL, MySQL, or Microsoft SQL
Server.

Each package contains `pipeline.sql`, `validation_queries.sql`, `parameters.json`, and a short
execution guide. Identifiers are quoted by the dialect adapter. User values never appear inside SQL;
the query uses named placeholders whose values are stored separately. Confirmed custom queries must
parse as exactly one read-only SELECT/CTE/UNION statement.

Transformations are compiled into ordered CTE stages. Selection, rename, casts, filters, stable
null-aware sorting, deterministic deduplication, replacement, null handling, derived fields,
aggregation, and masking have dialect-specific output. Validation queries cover not-null, unique,
range, allowed-values, and regex where the database has native regex support. SQL Server regex is
rejected before generation because SQL Server has no equivalent native regular-expression operator.

`Generated` becomes `Syntax Validated` only after sqlglot parses every emitted statement in the
selected dialect. It becomes `Sample Tested` only when a caller executes the query against a
disposable database and its rows match the shared Preview runtime. Automated tests execute the
portable query contract through an isolated in-memory database for all three dialect adapters;
syntax-only validation is never reported as sample-tested.

## JavaScript/Node.js boundary

The JavaScript generator produces `pipeline.mjs`, `runtime.mjs`, `pipeline_spec.json`,
`package.json`, a configuration example, README, sample runner, and Node unit test. Node.js 20 or
newer is required. CSV, JSON, JSON Lines, Excel, and Parquet file sources are represented; Excel and
Parquet packages receive only their required pinned dependencies. PostgreSQL, MySQL, and SQL Server
packages receive the corresponding adapter and resolve connection JSON from the environment variable
named by `connection_ref`. No credential value or local machine path is embedded.

The folder runtime supports quoted CSV values, the confirmed delimiter/encoding, deterministic
relative-glob discovery, recursive discovery, required/extra-column policy, fail-batch/quarantine/skip,
checksummed processed-file state, rejected rows, atomic overwrite/append, output path templates,
summary JSON, and scheduler exit codes.

The generated JavaScript runtime implements the same transformations and validations as Preview.
Decimal parsing and summation use scaled `BigInt` arithmetic to avoid binary floating-point drift;
datetime offsets and null semantics are preserved. Join is rejected before generation, while masking
is executed both for normal output rules and rejected-record protection.

Validation stages are explicit. Node `--check` validates every generated module. Sample execution
uses a fresh temporary workspace, Node's permission model, bounded heap, disabled dynamic string-code
generation, a sanitized environment, timeout, and unconditional workspace cleanup. Only exact parity
with Preview advances the package to `Sample Tested`.
