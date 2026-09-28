# MVP Scope Matrix

สถานะ: **Approved baseline — 2026-09-26**

คำจำกัดความ:

- `MVP Required`: ต้องเสร็จและผ่าน acceptance criteria ก่อน MVP release
- `Deferred`: เก็บใน Post-MVP backlog และไม่ถือเป็นตัวขวาง MVP
- ลำดับ `1` คือทำก่อนเพื่อสร้าง vertical slice; ลำดับที่สูงขึ้นคือขยายหลัง foundation ผ่าน

## Sources

| Capability | Proposed scope | Order | Rationale |
|---|---|---:|---|
| CSV | MVP Required | 1 | ใช้สร้าง vertical slice และพบได้บ่อย |
| JSON | MVP Required | 2 | รองรับข้อมูลกึ่งโครงสร้าง |
| JSON Lines | MVP Required | 3 | รองรับ record-oriented data |
| Excel | MVP Required | 4 | สำคัญสำหรับ Business users |
| Parquet | MVP Required | 5 | สำคัญสำหรับ data engineering |
| PostgreSQL | MVP Required | 6 | Database connector ตัวแรก |
| MySQL | MVP Required | 7 | Database connector ลำดับถัดไป |
| Microsoft SQL Server | MVP Required | 8 | รองรับ enterprise environment |

## Transformations

| Capability | Proposed scope | Order | Notes |
|---|---|---:|---|
| Include/Exclude/Rename | MVP Required | 1 | Vertical slice |
| Type Casting | MVP Required | 1 | Vertical slice |
| Filter/Sort | MVP Required | 1 | Vertical slice |
| Null Handling/Replace | MVP Required | 2 | Shared semantics required |
| Deduplicate | MVP Required | 2 | Stable ordering must be defined |
| Derived Field | MVP Required | 2 | Expression allowlist required |
| Aggregate | MVP Required | 3 | Decimal/null semantics required |
| Data Validation/Rejected Rows | MVP Required | 3 | Needed for trustworthy output |
| Sensitive Data Masking | MVP Required | 3 | Security requirement |
| Multi-source Join | Deferred | - | Complexity in cardinality, aliases and cross-source sampling |

## Generated Languages and Dialects

| Capability | Proposed scope | Order | Notes |
|---|---|---:|---|
| Python | MVP Required | 1 | Primary implementation and first vertical slice |
| PostgreSQL SQL | MVP Required | 2 | First SQL dialect |
| MySQL SQL | MVP Required | 3 | After shared SQL abstraction |
| SQL Server SQL | MVP Required | 4 | After shared SQL abstraction |
| JavaScript/Node.js | MVP Required | 5 | Must pass the same shared fixtures |

## Outputs

| Capability | Proposed scope | Order | Notes |
|---|---|---:|---|
| CSV | MVP Required | 1 | First vertical slice |
| JSON Lines | MVP Required | 2 | Streaming-friendly output |
| Parquet | MVP Required | 3 | Typed analytical output |
| SQL query text/result contract | MVP Required | 4 | Dialect-specific |
| Write to destination database | Deferred | - | Requires mutation and credential policy |

## Generated File Runtime

| Capability | Approved scope | Notes |
|---|---|---|
| Scan input folder on each run | MVP Required | Runtime receives `--input-dir` |
| Filename glob pattern | MVP Required | Relative, bounded pattern such as `*.csv` |
| Deterministic file ordering | MVP Required | Path ascending for reproducibility |
| Schema compatibility check | MVP Required | Strict by default; optional allowance for extra columns |
| Required/optional columns | MVP Required | Missing required columns follow failure policy |
| Quarantine/fail/skip policy | MVP Required | Quarantine is default |
| Processed-file tracking | MVP Required | Manifest/checksum or archive policy prevents duplicates |
| Execution summary and exit code | MVP Required | Supports scheduler/orchestrator integration |
| Continuous folder watcher | Deferred | Use external scheduler/orchestrator for MVP |

## Delivery Decision

สร้าง vertical slice ก่อน: `CSV → profiling → confirmed schema/specification → preview → Python generation → ZIP export` จากนั้นจึงขยาย capability ตามลำดับในตาราง

## Approval

| Role | Decision | Date |
|---|---|---|
| Project Owner | Approved baseline | 2026-09-26 |
| Engineering Lead | Review during implementation | - |
| Security/Compliance | Review security controls during Phase 2/15 | - |
