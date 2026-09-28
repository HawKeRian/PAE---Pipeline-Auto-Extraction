# Requirements Traceability Matrix

สถานะ: Phase 16 technical acceptance complete on 2026-09-27; external pilot/release evidence is tracked separately in Phase 17.

| Requirement | Scope | Progress phases | Planned acceptance evidence |
|---|---|---|---|
| PAE-FR-001 | MVP Required | 1.5, 4, 14 | Prototype usability, Project API and E2E tests |
| PAE-FR-002 | Per Scope Matrix | 5, 7, 14 | File contract and E2E tests |
| PAE-FR-003 | Per Scope Matrix | 6, 7, 14 | Connector integration tests |
| PAE-FR-004 | MVP Required | 7 | Profiling fixture suite |
| PAE-FR-005 | MVP Required | 7, 9, 15 | Masking and log-redaction tests |
| PAE-FR-006 | MVP Required | 1.5, 7, 14 | Prototype usability and schema confirmation E2E test |
| PAE-FR-007 | MVP Required | 1.5, 3, 8 | Prototype input test and Thai/English benchmark report |
| PAE-FR-008 | MVP Required | 3, 8 | Structured-output validation suite |
| PAE-FR-009 | MVP Required | 1.5, 3, 8, 14 | Prototype messaging, ambiguity benchmark and UI test |
| PAE-FR-010 | Per Scope Matrix | 2, 8, 9 | Capability matrix and rejection tests |
| PAE-FR-011 | MVP Required | 1.5, 8, 14 | Prototype flow and confirmation guard tests |
| PAE-FR-012 | MVP Required | 1.5, 9, 14 | Prototype usability and preview/rejected-row E2E tests |
| PAE-FR-013 | MVP Required | 10 | Python golden/parity tests |
| PAE-FR-014 | Per Scope Matrix | 11 | Dialect golden/parity tests |
| PAE-FR-015 | Per Scope Matrix | 12 | JavaScript golden/parity tests |
| PAE-FR-016 | MVP Required | 13 | Export manifest/package tests |
| PAE-FR-017 | MVP Required | 9-12, 15 | Sandbox and execution tests |
| PAE-FR-018 | MVP Required | 13, 15 | Secret scan and package inspection |
| PAE-FR-019 | MVP Required | 2, 4, 13, 14 | Revision invalidation/stale-result tests |
| PAE-FR-020 | MVP Required | 4, 15 | Audit event integration tests |
| PAE-FR-021 | MVP Required | 2, 5, 10, 13, 16 | Folder discovery, schema compatibility, idempotency and generated-package E2E tests |
| PAE-NFR-001 | MVP Required | 1, 16 | Health test and performance report |
| PAE-NFR-002 | MVP Required | 7, 16 | Profiling benchmark report |
| PAE-NFR-003 | MVP Required | 2, 4, 9, 16 | Queue/recovery test suite |
| PAE-NFR-004 | MVP Required | 4-6, 13, 15 | Secret scan/log-redaction evidence |
| PAE-NFR-005 | MVP Required | 5, 9, 15 | Retention tests |
| PAE-NFR-006 | MVP Required | 4, 15 | Cross-user denial tests |
| PAE-NFR-007 | MVP Required | 2, 9, 15 | Sandbox escape/resource-limit tests |
| PAE-NFR-008 | MVP Required | 9-12, 16 | Cross-generator parity suite |
| PAE-NFR-009 | MVP Required | 1 | Clean `ai_env` setup log |
| PAE-NFR-010 | MVP Required | 1, 16 | CI run evidence |
| PAE-NFR-011 | MVP Required | 2, 10, 16 | Repeat-run and processed-manifest test suite |

## Evidence Rules

- เปลี่ยน requirement เป็นผ่านได้เมื่อมี automated test หรือเอกสารตรวจรับที่เรียกซ้ำได้
- บันทึก commit/release identifier, environment และวันที่ของหลักฐาน
- เมื่อ scope เปลี่ยน ต้องแก้ PRD, Scope Matrix, Progress และตารางนี้ใน change เดียวกัน

## Phase 16 Acceptance Evidence

- ทุก `MVP Required` requirement ในตารางผ่าน automated suite; รายงานรวมอยู่ที่
  `docs/QA_REPORT.md` และ performance measurements อยู่ที่
  `reports/qa-benchmark-2026-09-27.json`.
- File ingestion ครบ CSV, JSON, JSON Lines, XLSX และ Parquet; database driver contract ครบ
  PostgreSQL, MySQL และ SQL Server และ PostgreSQL ผ่าน disposable TLS integration test.
- Cross-generator fixtures ครบ Python, JavaScript และ SQL ทั้ง PostgreSQL/MySQL/SQL Server;
  unsupported combinations และ advanced joins ยังคงเป็น Deferred ตาม `docs/SCOPE_MATRIX.md`.
- Folder runtime ผ่าน deterministic batch, required/optional/extra policies, mixed valid/invalid,
  repeat/modified/renamed inputs, atomic output, quarantine และ state recovery.
- Clean-environment evidence คือ wheel/sdist build และ Podman image smoke/restart drill;
  quality, security และ coverage gates ใช้คำสั่งที่ระบุใน `docs/QA_REPORT.md`.
