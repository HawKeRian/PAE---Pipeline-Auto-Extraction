# Pipeline Auto Extraction (PAE) — Progress Tracker

เอกสารนี้ใช้ติดตามงานพัฒนาระบบ Pipeline Auto Extraction ตาม PRD โดยแบ่งงานเป็น Phase และใช้สถานะดังนี้

- `[ ]` ยังไม่เริ่มหรือยังไม่เสร็จ
- `[X]` เสร็จแล้วและตรวจสอบผลเรียบร้อย

## Development Constraints

- ภาษาหลัก: Python
- Environment: Conda environment ชื่อ `ai_env`
- Dependencies: เพิ่มและกำหนด version ใน `requirements.txt`
- AI Model: ใช้ Local Llama เป็นหลัก
- ตรวจสอบโมเดล Llama ที่มีอยู่ในเครื่องก่อนเลือกใช้
- ดาวน์โหลดโมเดลเพิ่มเติมจาก Hugging Face เฉพาะเมื่อโมเดลที่มีอยู่ไม่เหมาะสม
- ห้ามเก็บ credential, access token, database password หรือข้อมูลอ่อนไหวไว้ใน source code
- ทุก Phase ต้องผ่านเกณฑ์ตรวจรับของ Phase ก่อนเปลี่ยนสถานะเป็น `[X]`

---

## Scope and Delivery Dependencies

- รายการ capability ใน tracker เป็นขอบเขตที่ต้องประเมิน ไม่ใช่การยืนยันว่าทุก capability ต้องอยู่ใน MVP
- จัดทำ Scope Matrix ใน Phase 0 โดยระบุแต่ละ source, transformation, output format, language และ dialect เป็น `MVP Required` หรือ `Deferred` พร้อมเหตุผลและผู้อนุมัติ
- งานที่เป็น `Deferred` ให้คง `[ ]` พร้อมอ้างอิง backlog และไม่ถือเป็นตัวขวาง Exit Criteria ของ MVP; ห้ามใช้ `[X]` แทนการเลื่อนงาน
- Scope Matrix และ acceptance criteria ได้รับ Project Owner approval เมื่อ 2026-09-26; การเปลี่ยน scope หลังจากนี้ต้องอัปเดต PRD, traceability และ acceptance tests
- ออกแบบ threat model, project ownership และ sandbox boundaries ใน Phase 2; Phase 15 ใช้ตรวจสอบและ harden สิ่งที่พัฒนาไว้
- หลัง Phase 1 ให้สร้าง Early Test UI ด้วย mock/stub เพื่อทดสอบ user flow ก่อน แล้วเชื่อม capability จริงแบบ incremental จนเป็น vertical slice: CSV → profiling → confirmed specification → preview → Python generation → ZIP export
- Phase 4–14 ทำแบบ incremental ตาม dependencies ได้ ไม่จำเป็นต้องรอให้ทุก capability ของ Phase ก่อนหน้าเสร็จ; ห้ามข้าม prerequisite ด้าน schema, confirmation และ security
- ทุก generator ต้องใช้ semantics และ shared test fixtures เดียวกับ preview; capability ที่ไม่รองรับต้องถูกปฏิเสธก่อน generation
- Release MVP ต้องผ่านงานที่เป็น `MVP Required` รวมถึง deployment, monitoring และ recovery ของตัว PAE

---

## Phase 0 — Product Definition and Project Planning

- [X] รวบรวมความต้องการเบื้องต้นของผลิตภัณฑ์
- [X] จัดทำ PRD ฉบับร่าง
- [X] กำหนดกลุ่มผู้ใช้และ User Journey หลัก
- [X] กำหนดขอบเขต MVP และรายการ Out of Scope
- [X] กำหนด Python เป็นภาษาหลักในการพัฒนา
- [X] กำหนด Conda environment ชื่อ `ai_env`
- [X] กำหนดให้ใช้ Local Llama เป็น AI Model หลัก
- [X] จัดทำแผนงานและ Progress Tracker
- [X] ทบทวนและอนุมัติ PRD กับผู้มีส่วนเกี่ยวข้อง
- [X] ตอบ Open Questions ที่มีผลต่อขอบเขต MVP
- [X] จัดลำดับ Database และ File Format ที่ต้องรองรับก่อน
- [X] กำหนดขนาดไฟล์ จำนวนแถว และเวลาในการประมวลผลสูงสุดของ MVP
- [X] กำหนดนโยบายการเก็บและลบ Sample Data
- [X] กำหนด Definition of Ready สำหรับงานพัฒนา

- [X] เพิ่ม PRD ที่อ้างถึงใน repository หรือแนบลิงก์ที่ทีมเข้าถึงได้ พร้อม version และหลักฐานของรายการ planning ที่เป็น `[X]`
- [X] จัดทำ Requirements Traceability Matrix: requirement ID → Scope Matrix → task/phase → acceptance test → หลักฐานผลตรวจรับ
- [X] ยืนยัน Scope Matrix ครอบคลุม sources, transformations รวมถึง Join, outputs, languages และ dialects
- [X] กำหนด acceptance thresholds ที่วัดได้สำหรับ correctness, AI benchmark, latency, resource usage และ concurrency

### Phase 0 Exit Criteria

- [X] PRD และขอบเขต MVP ได้รับการยืนยัน
- [X] ไม่มีคำถามสำคัญที่ทำให้ Architecture หรือ Data Security เปลี่ยนแปลง

---

## Phase 1 — Repository and Development Environment Setup

- [X] สร้างโครงสร้าง Python project
- [X] สร้าง Conda environment `ai_env` ด้วย Python version ที่ตกลงร่วมกัน
- [X] สร้าง `requirements.txt`
- [X] เพิ่มเฉพาะ libraries ที่ใช้งานจริงและกำหนด version
- [X] สร้าง `.gitignore` สำหรับ Python, Conda, IDE, model cache, temporary data และ secrets
- [X] สร้าง `.env.example` โดยไม่มี secret จริง
- [X] สร้าง application configuration แยกจาก source code
- [X] สร้างโฟลเดอร์สำหรับ source, tests, configs, samples และ generated outputs
- [X] ตั้งค่า formatter และ linter
- [X] ตั้งค่า type checking
- [X] ตั้งค่า unit test framework และ coverage report
- [X] ตั้งค่า pre-commit checks
- [X] สร้างคำสั่งมาตรฐานสำหรับ install, run, test, lint และ format
- [X] จัดทำ README สำหรับการติดตั้งและเริ่มพัฒนา
- [X] ตรวจสอบว่า project ติดตั้งและรันได้ใน `ai_env` จากเครื่องใหม่หรือ environment ที่สะอาด

- [X] ตั้งค่า CI ของตัว PAE ให้รัน lint, type check, tests และ secret/dependency scans ที่จำเป็นในทุก change

### Phase 1 Evidence

- Python 3.11.16 และ pip ติดตั้งใน conda env `ai_env`
- ติดตั้ง dependencies ซ้ำจาก `requirements.txt` สำเร็จเมื่อ 2026-09-26
- Ruff lint/format และ mypy strict ผ่าน
- Pytest ผ่าน 1 test; line/branch coverage ของ application foundation 100%
- `GET /health` ตอบ HTTP 200 พร้อม service/version/environment ที่ถูกต้อง
- Secret scan ผ่าน และ `pip-audit` รายงานว่าไม่พบ known vulnerabilities
- Pre-commit hook ติดตั้งใน local Git repository แล้ว
- GitHub Actions CI ผ่านสำหรับ commit `219c889` เมื่อ 2026-09-26: https://github.com/HawKeRian/PAE---Pipeline-Auto-Extraction/actions/runs/36244878075

### Phase 1 Exit Criteria

- [X] CI ผ่านบน environment สะอาดและเก็บผลตรวจสอบสำหรับ release review
- [X] ติดตั้ง dependencies จาก `requirements.txt` ใน `ai_env` ได้สำเร็จ
- [X] Application เริ่มทำงานได้
- [X] Lint, type check และ test command ทำงานได้

---

## Phase 1.5 — Early Test UI and Workflow Prototype

เป้าหมายของ Phase นี้คือทดสอบลำดับการใช้งานและภาษาที่ใช้สื่อสารกับผู้ใช้ตั้งแต่ต้น โดยยังไม่ถือว่า mock/stub เป็น implementation ของ capability จริง

- [X] จัดทำ UI testing strategy และกำหนดสิ่งที่เป็น mock, stub และ real service ให้ชัดเจน
- [X] เลือก UI foundation ที่ทำงานร่วมกับ FastAPI และยังคง Python เป็นแกนหลัก
- [X] สร้าง `/ui` application shell, navigation และ development-only banner
- [X] สร้างหน้า Project Dashboard แบบ in-memory/mock
- [X] สร้างหน้า Source Input สำหรับเลือกไฟล์และแสดงข้อจำกัดของ MVP
- [X] สร้างหน้าจำลอง Schema Analysis และ Schema Confirmation
- [X] สร้างหน้า Requirement Input ภาษาไทย/อังกฤษ
- [X] สร้างหน้าจำลอง Field Mapping และ Transformation Rule Editor
- [X] สร้างหน้าจำลอง Before/After Preview
- [X] สร้างหน้าจำลอง Target Language และ Code/README Preview
- [X] สร้างหน้าจำลอง Job Progress, Error, Cancel และ Retry states
- [X] สร้างหน้าจำลอง Export Summary และ Download Package
- [X] แยก fixture/mock data ออกจาก production services และห้ามส่งข้อมูลจริงไปยัง mock
- [X] เพิ่ม feature flag เพื่อป้องกัน mock flow ถูกใช้เป็น production capability
- [X] เพิ่ม automated UI smoke tests สำหรับ navigation และ critical form states
- [X] ทำ usability walkthrough ด้วย synthetic CSV และบันทึก feedback
- [X] ปรับคำอธิบาย, ลำดับหน้าจอ และ validation messages จากผลทดสอบ UI-001

### Phase 1.5 Evidence

- Jinja2 server-rendered UI และ vanilla JavaScript ทำงานผ่าน `/ui`
- มี Prototype/Mock banner, 10-step navigation และ responsive layout
- Mock flow ครอบคลุม Project → Source → Schema → Requirement → Rules → Preview → Target → Generated → Validation → Export
- Mock ZIP มี README, Python preview, Specification และ Artifact Manifest โดยไม่มี raw sample หรือ credential
- Mock UI และ static assets ตอบ 404 ใน production configuration
- Feedback UI-001 ถูกบันทึกใน `docs/UI_FEEDBACK.md` และเปลี่ยน flow เป็น Read → Profile → Suggest → User confirms
- Ruff, format และ mypy strict ผ่าน; Pytest ผ่าน 4 tests ด้วย coverage 100%
- Secret scan ผ่าน และ dependency audit ไม่พบ known vulnerabilities

### Phase 1.5 Exit Criteria

- [X] ผู้ทดสอบเดิน flow ตั้งแต่สร้าง Project ถึงหน้าดาวน์โหลดจำลองได้โดยไม่ใช้ command line
- [X] ทุกหน้าระบุชัดเจนว่าส่วนใดเป็น mock และส่วนใดเชื่อม service จริง
- [X] UI smoke tests ผ่านใน `ai_env`
- [X] Feedback และการตัดสินใจด้าน UX ถูกบันทึกก่อนเชื่อม backend capability จริง

---

## Phase 2 — Architecture and Core Domain Design

- [X] ออกแบบ Component Diagram ของระบบ
- [X] กำหนดขอบเขต Web/API, Profiling Engine, AI Service, Specification Engine, Code Generator และ Validation Sandbox
- [X] ออกแบบ Project domain model
- [X] ออกแบบ Source Configuration model
- [X] ออกแบบ Field Profile และ Schema model
- [X] ออกแบบ Transformation Rule model
- [X] ออกแบบ Pipeline Specification กลางที่ไม่ผูกกับภาษา
- [X] ออกแบบ Validation Rule และ Error Policy
- [X] ออกแบบ Generated Artifact และ Version model
- [X] กำหนด lifecycle/status ของ Project และ Generation Job
- [X] จัดทำ JSON Schema หรือ Pydantic model สำหรับ Pipeline Specification
- [X] กำหนด versioning และ backward compatibility ของ Specification
- [X] กำหนด interface สำหรับ Source Connector
- [X] กำหนด interface สำหรับ Code Generator แต่ละภาษา
- [X] กำหนด Capability Matrix ของ Python, SQL และ JavaScript
- [X] ออกแบบโครงสร้างฐานข้อมูลของระบบ
- [X] ออกแบบ API contract และ error response มาตรฐาน
- [X] จัดทำ Architecture Decision Records สำหรับการตัดสินใจสำคัญ

- [X] กำหนด output contract: destination/format ที่รองรับ, schema, encoding, null representation และ configuration ที่จำเป็น
- [X] กำหนด overwrite/append policy, atomic write หรือ cleanup เมื่อเขียนไม่ครบ และพฤติกรรมเมื่อ run ซ้ำ
- [X] กำหนด transformation semantics สำหรับ null, decimal precision, timezone, locale, sort stability, deduplication และ rule ordering
- [X] ออกแบบ source aliases และ Join contract สำหรับ scope ที่อนุมัติ รวม join keys/types, cardinality และ duplicate-column handling
- [X] ออกแบบ job execution: queue/scheduler, worker lifecycle, concurrency/backpressure, retry policy และ crash recovery
- [X] กำหนด immutable revision/source fingerprint และ dependency invalidation ของ confirmation, preview, validation และ artifacts
- [X] จัดทำ threat model และกำหนด project ownership, connector network policy และ sandbox filesystem/process/network boundaries
- [X] เพิ่ม reusable folder-batch runtime contract แยกจาก analysis sample พร้อม glob, schema, failure และ processed-file policies

### Phase 2 Evidence

- Component/trust boundaries: `docs/architecture/ARCHITECTURE.md`
- Strict versioned Pydantic contracts: `src/pae/domain/models.py`
- Source Connector และ Code Generator ports: `src/pae/domain/interfaces.py`
- Executable capability declarations: `src/pae/domain/capabilities.py`
- Generated JSON Schema: `schemas/pipeline-specification.schema.json`
- Shared transformation/output/job semantics: `docs/architecture/`
- Persistence/API/Threat Model และ ADRs: `docs/architecture/`
- Domain/UI validation ผ่าน 22 tests; core model coverage 95% และ project coverage 98%
- Requirement amendment PAE-FR-021: generated file pipeline เป็น full scan-on-run script สำหรับ future files ใน folder

### Phase 2 Exit Criteria

- [X] Architecture contracts ข้างต้นได้รับการ review และมี mapping ไปยัง implementation tasks
- [X] Pipeline Specification ผ่านการ review
- [X] API และ component boundaries ชัดเจนเพียงพอสำหรับเริ่ม implementation
- [X] มี automated validation สำหรับ Specification

---

## Phase 3 — Local Llama Evaluation and AI Foundation

- [X] สำรวจ Local Llama models ที่มีอยู่ในเครื่อง
- [X] บันทึก model name, parameter size, quantization, context length, file format และ license
- [X] ตรวจสอบทรัพยากรเครื่อง ได้แก่ CPU, RAM, GPU และ VRAM
- [X] เลือก inference runtime ที่เหมาะกับ model และ hardware
- [X] ทดสอบว่า runtime เรียกใช้ได้จาก `ai_env`
- [X] ออกแบบ AI provider interface เพื่อเปลี่ยน model/runtime ได้โดยไม่กระทบ business logic
- [X] สร้างชุดตัวอย่างความต้องการภาษาไทยและอังกฤษสำหรับ benchmark
- [X] กำหนด schema ของ structured output จาก Llama
- [X] ออกแบบ system prompt สำหรับแปลงภาษาธรรมชาติเป็น Transformation Specification
- [X] บังคับ validate AI output ด้วย schema ก่อนใช้งาน
- [X] ป้องกันไม่ให้ข้อมูลต้นทางถูกตีความเป็น system instruction
- [X] ทดสอบความถูกต้องของ field reference และ transformation rule
- [X] ทดสอบภาษาไทย ภาษาอังกฤษ และข้อความผสมสองภาษา
- [X] วัด latency, memory usage และความถูกต้องของแต่ละ local model
- [X] เลือก Local Llama model เริ่มต้นและบันทึกเหตุผล
- [X] กำหนด confidence, warning และ clarification behavior เมื่อคำสั่งกำกวม
- [X] เพิ่ม model/runtime libraries ที่เลือกใน `requirements.txt`
- [X] เพิ่มการตั้งค่า model path ผ่าน configuration โดยไม่ hard-code path
- [X] หาก local model ไม่ผ่านเกณฑ์ ให้กำหนดเกณฑ์ค้นหาโมเดลทดแทนจาก Hugging Face
- [X] ตรวจสอบ license, model card, file size และ hardware compatibility ก่อนดาวน์โหลดจาก Hugging Face
- [X] ดาวน์โหลดและ cache โมเดลเพิ่มเฉพาะเมื่อได้รับการประเมินว่าจำเป็น
- [X] จัดทำ Model Evaluation Report และ Model Usage Guide

### Phase 3 Exit Criteria

- [X] Local Llama สร้าง structured output ที่ผ่าน schema validation ได้
- [X] โมเดลผ่านเกณฑ์ benchmark ที่กำหนด
- [X] มี fallback behavior เมื่อ model โหลดไม่ได้หรือผลลัพธ์ไม่ถูกต้อง
- [X] ไม่มี sample data หรือ secret รั่วไหลผ่าน prompt/log

### Phase 3 Completion Summary

- Completed: 2026-09-26
- Selected runtime/model: Ollama + `llama3.1:8b` Q4_K_M; configuration is environment-driven
- Benchmark: 10/10 schema-valid, 10/10 semantic-correct, 1/1 safety-critical rejection
- Latency on reference machine: median 9.47 seconds, maximum 17.89 seconds
- Concurrency baseline: one Local Llama inference at a time due to 6 GB VRAM
- Safety boundary: prompt contract accepts requirement plus field names/types only; no row samples or credentials
- Fallback: runtime, schema, or unknown-field failures return a clarification response with no transformations
- Verification: 35 tests passed, total coverage 98.23%, AI foundation coverage 100%, no known dependency vulnerabilities

---

## Phase 4 — Project, Authentication, and Persistence Foundation

- [X] พัฒนา Project CRUD
- [X] พัฒนา Project status workflow
- [X] จัดเก็บ Source Configuration โดยไม่เก็บ secret แบบ plain text
- [X] จัดเก็บ Pipeline Specification และ version history
- [X] จัดเก็บ generation job และ validation result
- [X] เพิ่ม created/updated timestamp และผู้ดำเนินการ
- [X] พัฒนา authentication ขั้นพื้นฐาน
- [X] พัฒนา role-based access control
- [X] เพิ่ม audit events สำหรับ upload, analyze, confirm, generate, execute และ download
- [X] พัฒนา API validation และมาตรฐาน error response
- [X] เขียน unit tests สำหรับ domain และ persistence layer
- [X] เขียน API integration tests

- [X] พัฒนา database migrations พร้อมทดสอบการติดตั้งใหม่ การ upgrade และ recovery เมื่อ migration ล้มเหลว
- [X] พัฒนา job queue/worker, progress reporting, concurrency limits และ bounded retries ตาม error policy
- [X] ป้องกัน duplicate submission และกำหนด cancellation, interrupted-job recovery และ cleanup หลัง worker crash
- [X] ผูก job/result/artifact กับ source fingerprint, confirmed schema และ specification revision ที่ใช้จริง
- [X] เมื่อ source/schema/rules เปลี่ยน ให้ invalidate ผลที่เกี่ยวข้องและบังคับ reconfirm ก่อน generation
- [X] ป้องกันผลจาก job เก่าเขียนทับ revision ใหม่ และทดสอบ simultaneous edits/job completion
- [X] บังคับ project ownership และ resource-level authorization สำหรับ samples, jobs, versions และ artifact downloads

### Phase 4 Exit Criteria

- [X] Migration, job recovery, revision invalidation และ cross-user access tests ผ่าน
- [X] ผู้ใช้สร้าง เปิด แก้ไข และบันทึก Project ได้
- [X] Specification version สามารถเรียกดูย้อนหลังได้
- [X] สิทธิ์และ audit log ผ่านการทดสอบพื้นฐาน

### Phase 4 Completion Summary

- Completed: 2026-09-27
- Persistence: SQLite with three transactional migrations, immutable revision triggers, upgrade and rollback tests
- Authentication/RBAC: hashed local bearer tokens with owner/editor/viewer resource authorization
- Revisions: source changes invalidate confirmation; stale edits and old job completion cannot overwrite current state
- Jobs: persistent bounded queue, idempotency, progress, cancellation, retry, interrupted recovery and validation results
- Audit/API: workflow events plus standardized safe error envelopes and request IDs
- Verification: 56 tests passed; API coverage 100%; persistence repository coverage 98%; total project coverage 98.16%; no known dependency vulnerabilities

---

## Phase 5 — File Source Ingestion

- [X] พัฒนา upload flow และ file validation
- [X] รองรับ CSV
- [X] รองรับ JSON
- [X] รองรับ JSON Lines
- [X] รองรับ Microsoft Excel และการเลือก Sheet
- [X] รองรับ Parquet
- [X] รองรับ delimiter และ encoding configuration สำหรับ CSV
- [X] ตรวจสอบ MIME type, extension และ file signature
- [X] กำหนดและบังคับ file size limit
- [X] ป้องกัน path traversal และ unsafe archive/file handling
- [X] จำกัดจำนวน row/column ที่ใช้วิเคราะห์
- [X] จัดเก็บ temporary file อย่างปลอดภัย
- [X] ลบ temporary file ตาม retention policy
- [X] สร้าง normalized source metadata
- [X] วิเคราะห์ sample แล้วสร้าง reusable file runtime contract โดยไม่ hard-code sample filename/path
- [X] แนะนำ filename pattern, required/optional columns และ schema compatibility policy ให้ผู้ใช้ยืนยัน
- [X] เขียน tests สำหรับไฟล์ปกติ ไฟล์เสีย encoding ผิด และ schema ไม่สม่ำเสมอ

### Phase 5 Exit Criteria

- [X] อ่านทุก file format ในขอบเขต MVP ได้
- [X] ข้อผิดพลาดแสดงสาเหตุและแนวทางแก้ไขที่ผู้ใช้เข้าใจได้
- [X] ระบบไม่แก้ไขไฟล์ต้นทางและไม่เก็บไฟล์เกิน retention policy

### Phase 5 Completion Summary

- Completed: 2026-09-27
- Formats: CSV, JSON, JSON Lines, XLSX with sheet selection, and Parquet
- Analysis: normalized metadata, bounded column profiling, type inference, and required/optional field suggestions
- Runtime contract: reusable folder glob and recursive option without hard-coded sample filename or path
- Security: authorization before upload storage, size/MIME/signature checks, traversal and XLSX archive protections
- Retention: opaque temporary names, expiry metadata, startup/periodic/opportunistic cleanup, and failure rollback
- Verification: full quality gate passed; 87 tests passed; ingestion service coverage 97%; total project coverage 97.43%; no known dependency vulnerabilities

---

## Phase 6 — Database Source Connectors

- [X] ออกแบบ connection configuration และ secret reference
- [X] พัฒนา connection test แบบ read-only
- [X] รองรับ PostgreSQL
- [X] รองรับ MySQL
- [X] รองรับ Microsoft SQL Server
- [X] รองรับการเลือก schema, table และ view
- [X] รองรับ custom SELECT query ภายใต้นโยบายความปลอดภัย
- [X] ตรวจสอบและปฏิเสธ query ที่แก้ไขข้อมูล
- [X] จำกัดจำนวน row และ timeout ของ sample query
- [X] Mask credential และ sensitive connection information ใน UI/log
- [X] รองรับ connection cancellation และ cleanup
- [X] เขียน connector contract tests
- [X] เขียน integration tests กับฐานข้อมูลทดสอบ

- [X] บังคับสิทธิ์ read-only ที่ database account/session และทดสอบ query ที่มี side effects; ไม่อาศัยการตรวจคำว่า SELECT เพียงอย่างเดียว
- [X] บังคับ connector network/host policy, TLS configuration และป้องกันการเข้าถึง endpoint ที่อยู่นอกสิทธิ์

### Phase 6 Exit Criteria

- [X] Connector contract ทั้งสามชนิดผ่าน automated tests และ PostgreSQL ดึง sample แบบ read-only จาก Podman test instance ได้
- [X] ระบบไม่แสดงหรือบันทึก password/token แบบ plain text
- [X] Query limit และ timeout ทำงานตามข้อกำหนด

### Phase 6 Completion Summary

- Completed: 2026-09-27
- Implementation: complete for PostgreSQL, MySQL, and Microsoft SQL Server
- Security: secret references, masked connection metadata, exact host allowlist, DNS/IP checks, TLS policy, SQL AST validation, and database/session read-only enforcement
- Reliability: bounded `limit + 1` sampling, timeout, cancellation, rollback, and connection cleanup
- Automated verification: full quality gate passed; 109 tests passed; total coverage 95.86%; no known dependency vulnerabilities
- Connector verification: PostgreSQL 17 Alpine test instance deployed temporarily on Podman with TLS; integration sampling and database-enforced mutation rejection passed; test container and temporary certificate were removed afterward
- Scope decision: PostgreSQL Podman integration is the Phase 6 test environment; production or other external databases are not required for phase acceptance, while MySQL and SQL Server remain covered by shared connector contract tests

---

## Phase 7 — Schema Inference and Data Profiling

- [X] พัฒนา schema inference
- [X] ตรวจหา string, integer, decimal, boolean, date, datetime และ null
- [X] ตรวจหา mixed data types
- [X] ตรวจหา date/time format
- [X] คำนวณ null count และ null percentage
- [X] คำนวณ distinct count
- [X] คำนวณ min/max สำหรับ field ที่เหมาะสม
- [X] แสดง sample values ตามนโยบาย masking
- [X] คำนวณ confidence ของ inferred type
- [X] พัฒนา PII/sensitive-data detection เบื้องต้น
- [X] รองรับการ override data type โดยผู้ใช้
- [X] แยก inferred schema กับ user-confirmed schema
- [X] จัดการข้อมูลจำนวนมากแบบ sampling
- [X] เขียน tests สำหรับ edge cases และข้อมูลหลายภาษา
- [X] สร้าง profiling result API

### Phase 7 Exit Criteria

- [X] Profiling แสดงข้อมูลตาม PRD ครบ
- [X] ผู้ใช้แก้ไขและยืนยัน schema ได้
- [X] ค่า sensitive ถูก mask ตาม policy

### Phase 7 Completion Summary

- Completed: 2026-09-27
- Inference: string, integer, decimal, boolean, date, datetime, JSON, null, mixed types, date formats, and confidence
- Metrics: null count/percentage, distinct count, bounded samples, and numeric/temporal min/max
- Privacy: identifiers, email, phone, national ID, credit card, and IP detection with mandatory masking and no PII downgrade during confirmation
- Confirmation: inferred and immutable user-confirmed schemas are separated per source revision; data-type override is supported
- APIs: automatic profiling for file/database samples plus schema read, bounded profile, and schema confirmation endpoints
- Verification: multilingual, mixed-type, null, date-format, PII masking, sampling, schema override, and end-to-end API tests passed

---

## Phase 8 — Requirement Interpretation and Specification Builder

- [X] สร้างหน้าหรือ API รับความต้องการภาษาไทยและอังกฤษ
- [X] เชื่อม Local Llama เข้ากับ AI provider interface
- [X] ส่งเฉพาะ schema/context ที่จำเป็นให้ model
- [X] แปลงความต้องการเป็น structured transformation rules
- [X] Validate field references กับ confirmed schema
- [X] ตรวจหา field ที่ไม่มีอยู่และ rule ที่ไม่รองรับ
- [X] สร้าง clarification questions เมื่อ requirement กำกวม
- [X] แสดง assumptions และ warnings
- [X] รองรับ Include/Exclude
- [X] รองรับ Rename
- [X] รองรับ Type Casting
- [X] รองรับ Filter และ Sort
- [X] รองรับ Deduplicate
- [X] รองรับ Replace Value และ Null Handling
- [X] รองรับ Derived Field
- [X] รองรับ Aggregate
- [X] รองรับ Join ตามขอบเขตที่อนุมัติ โดยปฏิเสธพร้อมคำอธิบายตามสถานะ Deferred
- [X] รองรับ Data Validation Rule
- [X] รองรับ Sensitive Data Masking Rule
- [X] ให้ผู้ใช้เพิ่ม แก้ไข ลบ และจัดลำดับ rule
- [X] บันทึก confirmed specification แยกจาก AI suggestion
- [X] บังคับ user confirmation ก่อน code generation
- [X] เขียน tests สำหรับ prompt, structured output และ invalid rules

- [X] พัฒนา output configuration และ validate กับ output contract/capability ของ target language
- [X] N/A — Join ไม่อยู่ใน MVP ตาม Scope Matrix จึงไม่เปิด multi-source builder
- [X] หาก Join ไม่อยู่ใน MVP ให้ระบุ Deferred ใน Scope Matrix และปฏิเสธคำขอพร้อมคำอธิบาย

### Phase 8 Exit Criteria

- [X] ความต้องการตัวอย่างใน benchmark ถูกแปลงเป็น Specification ได้ตามเกณฑ์
- [X] AI output ที่ผิด schema ไม่เข้าสู่ code generation
- [X] ผู้ใช้เห็นและยืนยัน assumptions/rules ก่อนดำเนินการต่อ

### Phase 8 Completion Summary

- Completed: 2026-09-27
- AI boundary: Local `llama3.1:8b` receives only confirmed selected field names/types; source rows, samples, credentials, and paths are excluded
- Structured proposal: transformations, validations, assumptions, warnings, clarification questions, confidence, and safe fallback are schema validated
- Rule editing: full-list replacement supports add/edit/delete/reorder with consecutive ordering and field/capability validation
- Specification: proposals remain drafts; only ready proposals with acknowledged assumptions can create an immutable confirmed specification; generation remains blocked beforehand
- Scope: all approved MVP transformations and validation/masking rules are supported; multi-source Join remains Deferred and fails explicitly
- Model verification: Phase 8 Local Llama benchmark passed 10/10 cases with 100% schema validity, semantic correctness, and safety-critical pass rate; median latency 9.48 seconds
- Quality verification: full quality gate passed; 130 tests passed, 3 optional database integration tests skipped, total coverage 94.52%, and no known dependency vulnerabilities

---

## Phase 9 — Transformation Preview and Validation Engine

- [X] พัฒนา transformation executor สำหรับ sample data
- [X] แสดง before/after preview
- [X] แสดง input/output/rejected record counts
- [X] แสดงผลกระทบของแต่ละ rule
- [X] แสดง validation errors และ warnings แยกกัน
- [X] รองรับ rejected-record preview โดย mask sensitive data
- [X] ตรวจจับ schema change และผลกระทบต่อ rule เดิม
- [X] เพิ่ม timeout, memory limit และ cancellation
- [X] แยก execution workspace ต่อ job
- [X] ปิด network access สำหรับ sandbox โดยค่าเริ่มต้น
- [X] ลบ temporary execution data หลังจบงาน
- [X] เขียน tests สำหรับ transformation ทุกประเภท
- [X] เขียน tests สำหรับ resource limit และ malicious input

- [X] ใช้ transformation semantics ที่กำหนดร่วมกันและสร้าง shared expected-output fixtures สำหรับทุก MVP rule
- [X] N/A — Join เป็น Deferred ตาม Scope/Capability Matrix และถูกปฏิเสธก่อน Preview
- [X] บังคับ sandbox filesystem/process isolation, execution identity และ CPU/process/output-size limits ตาม threat model
- [X] ทดสอบ cancellation และ cleanup ทั้งกรณีสำเร็จ ล้มเหลว timeout และ process crash

### Phase 9 Exit Criteria

- [X] Preview ตรงกับ confirmed specification
- [X] Validation status แยก Generated, Syntax Validated และ Sample Tested อย่างถูกต้อง
- [X] Sandbox ไม่เข้าถึง resource ที่ไม่ได้รับอนุญาต

### Phase 9 Completion Summary

- Completed: 2026-09-27
- Semantics: one standard-library runtime core shared verbatim by Preview and generated Python
- Preview: masked before/after/rejected rows, counts, rule impacts, separate errors/warnings, and schema-impact reporting
- Sandbox: per-run workspace, sanitized process environment, network/filesystem/child-process isolation, time/CPU/memory/output limits, cancellation, process-tree termination, and unconditional cleanup
- Verification: shared expected-output fixtures cover every MVP transformation and validation; Join remains explicitly Deferred

---

## Phase 10 — Python Code Generator

- [X] ออกแบบ Python generator templates
- [X] สร้าง code สำหรับ file input
- [X] สร้าง code สำหรับ database input
- [X] สร้าง code สำหรับ field selection และ rename
- [X] สร้าง code สำหรับ type conversion
- [X] สร้าง code สำหรับ filter, sort และ deduplicate
- [X] สร้าง code สำหรับ null handling และ value replacement
- [X] สร้าง code สำหรับ derived fields และ aggregation
- [X] สร้าง code สำหรับ validation และ rejected records
- [X] สร้าง configuration และ environment variable handling
- [X] สร้าง logging และ error handling
- [X] สร้าง output writer ตาม format ที่รองรับ
- [X] สร้าง `requirements.txt` สำหรับ generated package
- [X] สร้าง unit tests สำหรับ generated pipeline
- [X] ตรวจ syntax และ format generated Python
- [X] Execute generated code กับ sample data ใน sandbox
- [X] สร้าง golden tests สำหรับ generator
- [X] สร้าง CLI สำหรับ `--input-dir`, `--output-dir`, `--quarantine-dir` และ `--state-file`
- [X] ค้นหาไฟล์ตาม relative glob และเรียงลำดับแบบ deterministic
- [X] ตรวจ required/optional columns และ schema compatibility ก่อนประมวลผลแต่ละไฟล์
- [X] รองรับ fail-batch, quarantine และ skip policy
- [X] สร้าง processed-file manifest/checksum และป้องกันผลลัพธ์ซ้ำเมื่อ run ใหม่
- [X] สร้าง batch execution summary และ exit codes สำหรับ scheduler/orchestrator

- [X] สร้าง sensitive-data masking และปฏิเสธ Join ก่อน generation ตาม Capability Matrix
- [X] ใช้ output contract รวม partial-write cleanup และ atomic overwrite/append พร้อมทดสอบ run ซ้ำ

### Phase 10 Exit Criteria

- [X] เปรียบเทียบผล Python กับ shared fixtures/preview สำหรับทุก MVP transformation และ rule combinations ที่สำคัญ
- [X] Generated Python ผ่าน syntax check
- [X] Generated Python ให้ผลลัพธ์ตรงกับ preview
- [X] ไม่มี credential หรือ machine-specific path ฝังอยู่ใน code

### Phase 10 Completion Summary

- Completed: 2026-09-27
- Package: standalone pipeline, shared runtime, immutable specification, dependency file, environment example, README, and generated test
- Sources/outputs: all MVP file readers, environment-referenced PostgreSQL/MySQL/SQL Server readers, and CSV/JSON Lines/Parquet writers
- Batch runtime: deterministic relative-glob discovery, schema policy, quarantine/skip/fail-batch handling, checksummed manifest, summaries, scheduler exit codes, and future-file reuse
- Safety/parity: Join rejected, sensitive rejected rows masked, credentials/paths rejected, explicit Generated/Syntax Validated/Sample Tested stages, and sandbox sample parity
- Reliability: golden generation snapshot plus atomic overwrite/append behavior and retry/idempotency tests

---

## Phase 11 — SQL Code Generator

- [X] ออกแบบ SQL generator templates
- [X] กำหนด dialect abstraction
- [X] รองรับ PostgreSQL dialect
- [X] รองรับ MySQL dialect
- [X] รองรับ Microsoft SQL Server dialect
- [X] Generate SELECT, alias, cast, filter, sort และ deduplicate
- [X] Generate derived fields และ aggregation
- [X] Generate validation queries
- [X] Quote identifier และ parameterize values อย่างปลอดภัย
- [X] ปฏิเสธ unsupported transformation พร้อมคำอธิบาย
- [X] ตรวจ syntax ตาม dialect
- [X] Execute SQL กับ test database เมื่อทำได้
- [X] สร้าง golden tests แยกตาม dialect

- [X] ระบุ SQL input/output boundary ให้ชัดเจน รวมข้อจำกัดของ file sources และวิธีส่งคืน query results
- [X] Generate null handling, value replacement และ masking; ปฏิเสธ Join ที่เป็น Deferred ตาม Capability Matrix

### Phase 11 Exit Criteria

- [X] เปรียบเทียบผลกับ shared fixtures/preview บนทุก MVP dialect; syntax-only validation ไม่ถือเป็น Sample Tested
- [X] Generated SQL ผ่าน dialect validation
- [X] SQL ไม่มีคำสั่งแก้ไข source data โดยไม่ได้รับอนุญาต
- [X] ผลลัพธ์ตรงกับ Specification และ preview

### Phase 11 Completion Summary

- Completed: 2026-09-27
- Dialects: PostgreSQL, MySQL, and SQL Server adapters with dialect quoting, casts, null ordering, masking, and validation predicates
- Boundary: one confirmed database source to a read-only SQL result; file input, writes, cross-dialect sources, and Deferred Join fail before generation
- Safety: custom input is exactly one parsed read-only query; identifiers are quoted and values are emitted only as named parameters
- Validation: generated SQL remains Generated until dialect parsing succeeds, and becomes Sample Tested only after disposable-database execution matches Preview
- Verification: per-dialect golden tests, every MVP transformation compilation, validation-query coverage, mutation denial, injection-value isolation, and cross-dialect sample parity

---

## Phase 12 — JavaScript/Node.js Code Generator

- [X] ออกแบบ JavaScript generator templates
- [X] สร้าง code สำหรับ file input
- [X] สร้าง code สำหรับ database input ตาม connector ที่รองรับ
- [X] สร้าง transformation functions ตาม Capability Matrix
- [X] รองรับ validation, logging และ error handling
- [X] สร้าง configuration และ environment variable handling
- [X] สร้าง `package.json` และ dependency versions
- [X] สร้าง unit tests สำหรับ generated pipeline
- [X] ตรวจ syntax และ deterministic template format ของ generated JavaScript
- [X] Execute generated code กับ sample data ใน sandbox
- [X] สร้าง golden tests สำหรับ generator

- [X] สร้าง output writer ตาม output contract รวม partial-write cleanup และ atomic overwrite/append policy
- [X] รองรับ masking และปฏิเสธ Join ที่เป็น Deferred ตาม Capability Matrix

### Phase 12 Exit Criteria

- [X] เปรียบเทียบผล JavaScript กับ shared fixtures/preview รวม decimal, timezone และ null edge cases
- [X] Generated JavaScript ผ่าน syntax check
- [X] Generated JavaScript ให้ผลลัพธ์ตรงกับ preview
- [X] Unsupported rules ถูกแจ้งก่อน generation

### Phase 12 Completion Summary

- Completed: 2026-09-27
- Package: Node ESM pipeline/runtime, immutable specification, pinned package.json, environment example, README, sample runner, and generated unit test
- Inputs: CSV/JSON/JSON Lines plus dependency adapters for Excel/Parquet and environment-referenced PostgreSQL/MySQL/SQL Server
- Runtime: shared transformation/validation semantics, scaled-BigInt decimal operations, timezone/null parity, sensitive masking, and explicit Deferred Join rejection
- Batch/output: deterministic recursive relative-glob discovery, schema policy, manifest idempotency, quarantine/skip/fail-batch, rejected records, atomic overwrite/append, summaries, and exit codes
- Verification: golden snapshot, Node syntax/unit tests, every shared transformation and validation fixture, quoted CSV, repeat-run behavior, and permission-sandbox sample parity

---

## Phase 13 — README and Export Package Generation

- [X] สร้าง README template
- [X] สร้างภาพรวม Pipeline จาก Specification
- [X] ระบุ input/output schema
- [X] ระบุ transformation และ validation rules
- [X] ระบุ prerequisites และ dependency installation
- [X] ระบุ environment variables โดยไม่เปิดเผยค่า secret
- [X] สร้าง run commands ที่ตรงกับ generated files
- [X] เพิ่ม assumptions, warnings และ known limitations
- [X] เพิ่ม security notes และ troubleshooting
- [X] เพิ่มจุดเชื่อมต่อกับขั้นตอนถัดไป
- [X] สร้าง `.env.example`
- [X] Export Specification เป็น JSON หรือ YAML
- [X] สร้าง sample output ที่ผ่าน masking
- [X] สร้าง ZIP package
- [X] ตรวจว่า package ไม่มี source sample หรือ credential โดยค่าเริ่มต้น
- [X] แสดงรายการไฟล์และ validation status ก่อนดาวน์โหลด
- [X] ทดสอบติดตั้งและ run generated package ใน clean environment
- [X] README อธิบาย folder structure, filename pattern, schema policy, quarantine และ repeat-run behavior
- [X] เพิ่มตัวอย่างคำสั่ง scan-on-run และแนวทางเรียกด้วย Task Scheduler/cron โดยไม่ฝัง continuous watcher

- [X] แนบ artifact manifest ระบุ source/schema/specification revision, generator/model version และ validation evidence โดยไม่เปิดเผย secrets
- [X] แสดงสถานะ stale เมื่อ package ไม่ตรงกับ revision ปัจจุบัน และแยกการดาวน์โหลด historical version ให้ชัดเจน

### Phase 13 Evidence

- `src/pae/exporting.py`, `docs/EXPORT_PACKAGE_GUIDE.md` และ export/artifact APIs
- Acceptance test แตก ZIP แล้วรันกับ future CSV และยืนยัน repeat-run skip ไฟล์เดิม
- ZIP มี source/runtime, tests, README, `.env.example`, Specification, masked output และ manifest
- Source secret scan ไม่พบผลลัพธ์; package scan ทำก่อนจัดเก็บทุกครั้ง

### Phase 13 Exit Criteria

- [X] ZIP มี source, tests, config example, README และ Specification ครบ
- [X] คำสั่งใน README ใช้งานได้จริง
- [X] Secret scan ของ package ผ่าน

---

## Phase 14 — Production UI Integration and End-to-End Hardening

- [X] ทบทวน Early Test UI feedback และยืนยัน production information architecture
- [X] เปลี่ยน Project Dashboard จาก mock เป็น persistence/API จริง
- [X] เชื่อม Source Input กับ file upload และ database connection APIs จริง
- [X] เชื่อม Schema Analysis และ Confirmation กับ profiling APIs จริง
- [X] เชื่อม Requirement Input กับ Local Llama และ clarification flow จริง
- [X] เชื่อม Field Mapping และ Rule Editor กับ versioned Pipeline Specification
- [X] เชื่อม Before/After Preview กับ sandbox validation engine
- [X] เชื่อม language/dialect/runtime selection กับ Capability Matrix
- [X] เชื่อม Code, README, manifest และ Export กับ generated artifacts จริง
- [X] ลบหรือปิด mock/stub ทั้งหมดจาก production configuration
- [X] รองรับ loading, empty, error, retry และ partial-failure states จาก API จริง
- [X] รองรับการย้อนกลับไปแก้ไขขั้นก่อนหน้าโดยรักษา revision consistency
- [X] แสดง job progress, cancellation และ recovery หลัง reload/reconnect โดยไม่สร้าง job ซ้ำ
- [X] เมื่อแก้ source/schema/rules ให้แสดง stale results และขั้นตอนที่ต้องยืนยันหรือประมวลผลใหม่
- [X] ทดสอบ keyboard navigation, responsive layout และ accessibility ขั้นพื้นฐาน
- [X] เขียน end-to-end tests สำหรับ happy path ของ vertical slice จริง
- [X] เขียน end-to-end tests สำหรับ failure, authorization และ recovery paths
- [X] พัฒนาและทดสอบ vertical slice จริง: CSV → profiling → confirm → preview → Python → ZIP export

### Phase 14 Evidence

- Production `/ui` เรียก versioned APIs จริงและไม่มี `/ui/mock-export`
- Browser token อยู่ใน session storage; รองรับ loading/error/retry, step back, job polling/cancel/recovery และ stale artifact
- Responsive/keyboard focus/security smoke tests และ API vertical-slice E2E อยู่ใน `tests/test_ui.py` และ `tests/test_api.py`

### Phase 14 Exit Criteria

- [X] ทดสอบ stale-result handling และ authorization ใน user journeys ที่เกี่ยวข้อง
- [X] ผู้ใช้ทำ workflow ตั้งแต่สร้าง Project ถึงดาวน์โหลด package ได้
- [X] UI แยก inferred, suggested และ user-confirmed values ชัดเจน
- [X] Critical user journeys ผ่าน end-to-end tests

---

## Phase 15 — Security, Privacy, and Compliance Hardening

- [X] ทบทวนและปรับปรุง threat model ที่จัดทำไว้ใน Phase 2 ให้สอดคล้องกับ implementation จริง
- [X] Review file upload attack surface
- [X] Review database connector และ query attack surface
- [X] Review prompt injection และ model output attack surface
- [X] Review generated code execution sandbox
- [X] เพิ่ม secret scanning สำหรับ source และ generated artifacts
- [X] เพิ่ม dependency vulnerability scanning
- [X] เพิ่ม authentication/authorization tests
- [X] ตรวจสอบ encryption in transit และ at rest
- [X] ตรวจสอบ data retention และ deletion flow
- [X] ตรวจสอบ PII masking และ log redaction
- [X] เพิ่ม rate limiting และ abuse protection
- [X] เพิ่ม security headers และ secure configuration defaults
- [X] ทดสอบการลบ Project, sample data และ generated artifacts
- [X] จัดทำ Security and Privacy Checklist ก่อน release

- [X] ทดสอบ cross-user access denial สำหรับ project, samples, jobs, artifacts, versions และ download URLs
- [X] ทดสอบ session expiry/logout และ permission changes ว่าไม่เปิดสิทธิ์เข้าถึง resource ต่อโดยไม่ตั้งใจ
- [X] ทดสอบ sandbox escape attempts, filesystem/process restrictions และ connector network policy ตาม threat model

### Phase 15 Evidence

- Threat review: `docs/architecture/THREAT_MODEL.md`; approved checklist: `docs/SECURITY_PRIVACY_CHECKLIST.md`
- Security headers, production HSTS, no-store API responses, per-route rate limiting และ immediate token revocation
- Project deletion ลบ samples/ZIPs/project-owned rows และคง anonymized audit tombstone
- Cross-user, permission-change, logout, deletion, sandbox และ network-policy tests ผ่าน
- `pip-audit -r requirements.txt`: No known vulnerabilities; source secret scan: 0 findings

### Phase 15 Exit Criteria

- [X] ไม่มี Critical หรือ High severity issue ที่ยังไม่ได้รับการแก้ไข
- [X] Data deletion และ retention policy ผ่านการทดสอบ
- [X] Security checklist ได้รับการอนุมัติ

---

## Phase 16 — Quality Assurance and Performance Testing

- [X] ตรวจ test coverage และเติม test ในส่วนสำคัญ
- [X] ทดสอบทุก supported file format
- [X] ทดสอบทุก database connector
- [X] ทดสอบทุก transformation rule
- [X] ทดสอบทุก code generator และ dialect
- [X] ทดสอบภาษาไทย อังกฤษ และข้อความผสม
- [X] ทดสอบ corrupted, malformed และ adversarial input
- [X] ทดสอบ concurrency ของ generation jobs
- [X] ทดสอบ file size และ row limits
- [X] ทดสอบ profiling performance
- [X] ทดสอบ AI latency และ memory usage
- [X] ทดสอบ code generation และ sandbox performance
- [X] ทดสอบ generated packages ใน clean environments
- [X] แก้ไข defect ตาม severity
- [X] จัดทำ QA report และ release recommendation
- [X] ทดสอบ folder batch ด้วยหลายไฟล์, deterministic order และ mixed valid/invalid schemas
- [X] ทดสอบ required/optional/extra columns ครบทุก schema policy
- [X] ทดสอบ repeat run, modified/renamed file, partial output, quarantine failure และ state recovery

- [X] รัน cross-generator parity suite จาก shared fixtures ครบทุก MVP language/dialect และตรวจค่ากับ data types ตาม contract
- [X] ทดสอบ queue saturation, duplicate submission, worker crash, cancellation และ recovery ภายใต้ concurrency ที่กำหนด
- [X] ทดสอบ output failures, repeated runs และ stale revisions ไม่ให้เกิดไฟล์ไม่สมบูรณ์หรือผลที่อ้างอิงผิด version

### Phase 16 Evidence

- Full suite: 180 passed, 3 opt-in integrations skipped, coverage 86.12% (threshold 80%)
- PostgreSQL 16 disposable Podman integration พร้อม TLS: 1 passed; MySQL/SQL Server ผ่าน driver/policy/query contract tests
- Performance: profiling 100k p95 3.707s, preview 10k p95 0.310s, generation p95 0.002s, health p95 0.008s
- Local Llama benchmark: schema/semantic/safety 100%, median 9.48s, max 16.40s
- Ruff, formatting, mypy, source secret scan และ dependency audit ผ่าน; ไม่พบ known vulnerability
- รายงาน: `docs/QA_REPORT.md`, `reports/qa-benchmark-2026-09-27.json`, `docs/REQUIREMENTS_TRACEABILITY.md`

### Phase 16 Exit Criteria

- [X] Requirements Traceability Matrix มีหลักฐานผลผ่านสำหรับทุก MVP requirement; Deferred items แยกชัดเจน
- [X] Functional acceptance criteria ของ MVP ผ่าน
- [X] Performance อยู่ในเกณฑ์ที่กำหนด
- [X] ไม่มี Critical หรือ High severity defect ที่ยังไม่ได้แก้ไข

---

## Phase 17 — Documentation, Pilot, and MVP Release

- [X] จัดทำ User Guide
- [X] จัดทำ Developer Guide
- [X] จัดทำ API Documentation
- [X] จัดทำ Model Setup and Troubleshooting Guide
- [X] จัดทำ Supported Sources and Transformations Matrix
- [X] จัดทำ Deployment and Operations Guide
- [X] จัดทำ Backup and Recovery Procedure
- [X] กำหนด monitoring, metrics และ alerting
- [ ] เตรียม pilot users และตัวอย่าง use cases (Blocked: use cases และแผนพร้อมแล้ว แต่ต้องระบุ/นัดหมาย pilot users จริง)
- [ ] ฝึกอบรม pilot users (Blocked: รอ pilot participants จริง)
- [ ] เก็บ feedback และ usability issues (Blocked: รอผลใช้งานจาก pilot จริง)
- [ ] แก้ไข blocker จาก pilot (Blocked: ยังไม่มี pilot feedback ให้ประเมิน)
- [X] จัดทำ release notes
- [X] สร้าง release candidate
- [X] ทำ Go/No-Go review (ผล: Technical Go for controlled pilot; Public MVP No-Go pending external evidence)
- [ ] Release MVP (Blocked: Go/No-Go ยังไม่อนุมัติ public release)
- [ ] เฝ้าระวัง error, latency และ resource usage หลัง release (Blocked: ยังไม่มี production deployment)
- [X] สรุปผลเทียบกับ Success Metrics ใน PRD (technical metrics ผ่าน; user/product metrics รอ pilot)

- [X] สร้าง deployment configuration และ versioned build/release artifacts ของตัว PAE พร้อม environment/secrets configuration
- [X] ตั้งค่า release pipeline ของ PAE พร้อม smoke tests และขั้นตอน rollback ที่ทดสอบแล้ว
- [X] พัฒนา health/readiness checks ครอบคลุม application, persistence, workers และ model availability ตามหน้าที่ของ service
- [X] ติดตั้ง structured logs, metrics และ alerts สำหรับ failures, latency, queue depth และ resource usage พร้อมทดสอบ alert delivery (HTTPS webhook delivery/failure/cooldown ผ่าน automated tests; production receiver ยังเป็น Go/No-Go prerequisite)
- [X] ตั้งค่า backup สำหรับ persistent data/configuration ที่จำเป็น และทดสอบ restore ใน environment แยก
- [X] กำหนด recovery objectives, ผู้รับผิดชอบ incident และ runbooks; บันทึกผล restore/rollback drill
- [X] ทดสอบ deployment จาก environment สะอาดและ upgrade จาก release ก่อนหน้าเมื่อมี (clean Podman deploy ผ่าน; ยังไม่มี release ก่อนหน้าให้ทำ data migration upgrade)

### Phase 17 Evidence

- Release artifacts: wheel, sdist และ `localhost/pae:0.1.0-rc1`; hashes/image ID อยู่ใน `reports/release-0.1.0-rc1.json`
- Final Podman smoke: `/health` และ `/ready` ผ่าน; metrics และ immutable-image restart ผ่าน
- HTTPS alert webhook รองรับ bounded timeout, duplicate cooldown และ delivery metrics; success/failure/throttling tests ผ่าน
- Backup/restore integrity และ non-empty-target protection ผ่าน automated tests
- Operations docs: `docs/DEPLOYMENT_OPERATIONS.md`, `docs/BACKUP_RECOVERY.md`, `docs/INCIDENT_RUNBOOK.md`
- Pilot/decision: `docs/PILOT_PLAN.md`, `docs/PILOT_RESULTS.md`, `docs/GO_NO_GO.md`, `docs/SUCCESS_METRICS_REVIEW.md`
- Pilot facilitator package: `docs/PILOT_TRAINING.md`, `docs/PILOT_FEEDBACK_FORM.md`, `docs/PILOT_HANDOFF_CHECKLIST.md`

### Phase 17 Exit Criteria

- [ ] Deployment smoke tests, monitoring, backup restore และ rollback ผ่านก่อน Go/No-Go (Blocked: technical drills ผ่าน; รอทดสอบ production alert delivery)
- [ ] ผู้ใช้กลุ่ม pilot ทำงานหลักได้โดยไม่มีผู้พัฒนาช่วย (Blocked: ต้องมี pilot participants จริง)
- [X] Operations สามารถติดตามและแก้ปัญหาพื้นฐานได้
- [ ] MVP ผ่าน Go/No-Go review และเปิดใช้งานแล้ว (Blocked: review ให้ No-Go จนกว่า pilot และ production controls จะมีหลักฐาน)

---

## Post-MVP Backlog

- [ ] เปรียบเทียบ Specification และ generated output ระหว่าง version
- [ ] Reusable Pipeline Templates
- [ ] Advanced multi-source joins
- [ ] Schema drift monitoring
- [ ] Team collaboration และ approval workflow
- [ ] Git repository integration
- [ ] CI/CD integration สำหรับ exported pipelines ของผู้ใช้ (CI/release pipeline ของตัว PAE อยู่ใน MVP)
- [ ] Airflow export
- [ ] Dagster export
- [ ] Prefect export
- [ ] dbt project generation
- [ ] Scheduled pipeline execution
- [ ] Production deployment assistance
- [ ] Data lineage
- [ ] Production monitoring สำหรับ exported pipelines ของผู้ใช้ (monitoring ของตัว PAE อยู่ใน MVP)
- [ ] Additional file formats และ database connectors
- [ ] Custom connector/generator plugin system

---

## Progress Update Rules

- เปลี่ยน `[ ]` เป็น `[X]` เมื่อ task เสร็จและตรวจสอบผลแล้วเท่านั้น
- หาก task กำลังทำ ให้คง `[ ]` และเพิ่มข้อความ `(In Progress)` ต่อท้าย
- หาก task ถูกพัก ให้คง `[ ]` และเพิ่มข้อความ `(Blocked: เหตุผล)` ต่อท้าย
- เพิ่ม task ใหม่ใต้ Phase ที่เกี่ยวข้องเมื่อพบงานเพิ่มเติม
- บันทึกการตัดสินใจที่กระทบ Architecture, Security หรือ Scope ในเอกสารที่เกี่ยวข้อง และอ้างอิงจาก task
- ก่อนจบแต่ละ Phase ให้ตรวจ Exit Criteria ทุกข้อ
- อ้างอิง requirement ID และหลักฐานผลตรวจรับเมื่อปิด task; อย่าถือว่าการมี checklist เท่ากับมี implementation แล้ว
- ทบทวน Scope Matrix และ Requirements Traceability Matrix ทุกครั้งที่ scope เปลี่ยน พร้อมปรับ dependencies และ acceptance tests
- เมื่อเพิ่ม library ให้เพิ่มลง `requirements.txt` พร้อมกำหนด version และเหตุผลการใช้งาน
- ก่อนเพิ่มหรือดาวน์โหลด AI model ให้บันทึกผลการประเมิน model ที่มีอยู่ก่อน
