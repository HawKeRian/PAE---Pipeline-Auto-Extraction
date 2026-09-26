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
- GitHub Actions workflow ถูกสร้างแล้ว แต่ยังไม่มี remote CI run evidence

### Phase 1 Exit Criteria

- [ ] CI ผ่านบน environment สะอาดและเก็บผลตรวจสอบสำหรับ release review
- [X] ติดตั้ง dependencies จาก `requirements.txt` ใน `ai_env` ได้สำเร็จ
- [X] Application เริ่มทำงานได้
- [X] Lint, type check และ test command ทำงานได้

---

## Phase 1.5 — Early Test UI and Workflow Prototype

เป้าหมายของ Phase นี้คือทดสอบลำดับการใช้งานและภาษาที่ใช้สื่อสารกับผู้ใช้ตั้งแต่ต้น โดยยังไม่ถือว่า mock/stub เป็น implementation ของ capability จริง

- [ ] จัดทำ UI testing strategy และกำหนดสิ่งที่เป็น mock, stub และ real service ให้ชัดเจน
- [ ] เลือก UI foundation ที่ทำงานร่วมกับ FastAPI และยังคง Python เป็นแกนหลัก
- [ ] สร้าง `/ui` application shell, navigation และ development-only banner
- [ ] สร้างหน้า Project Dashboard แบบ in-memory/mock
- [ ] สร้างหน้า Source Input สำหรับเลือกไฟล์และแสดงข้อจำกัดของ MVP
- [ ] สร้างหน้าจำลอง Schema Analysis และ Schema Confirmation
- [ ] สร้างหน้า Requirement Input ภาษาไทย/อังกฤษ
- [ ] สร้างหน้าจำลอง Field Mapping และ Transformation Rule Editor
- [ ] สร้างหน้าจำลอง Before/After Preview
- [ ] สร้างหน้าจำลอง Target Language และ Code/README Preview
- [ ] สร้างหน้าจำลอง Job Progress, Error, Cancel และ Retry states
- [ ] สร้างหน้าจำลอง Export Summary และ Download Package
- [ ] แยก fixture/mock data ออกจาก production services และห้ามส่งข้อมูลจริงไปยัง mock
- [ ] เพิ่ม feature flag เพื่อป้องกัน mock flow ถูกใช้เป็น production capability
- [ ] เพิ่ม automated UI smoke tests สำหรับ navigation และ critical form states
- [ ] ทำ usability walkthrough ด้วย synthetic CSV และบันทึก feedback
- [ ] ปรับคำอธิบาย, ลำดับหน้าจอ และ validation messages จากผลทดสอบ

### Phase 1.5 Exit Criteria

- [ ] ผู้ทดสอบเดิน flow ตั้งแต่สร้าง Project ถึงหน้าดาวน์โหลดจำลองได้โดยไม่ใช้ command line
- [ ] ทุกหน้าระบุชัดเจนว่าส่วนใดเป็น mock และส่วนใดเชื่อม service จริง
- [ ] UI smoke tests ผ่านใน `ai_env`
- [ ] Feedback และการตัดสินใจด้าน UX ถูกบันทึกก่อนเชื่อม backend capability จริง

---

## Phase 2 — Architecture and Core Domain Design

- [ ] ออกแบบ Component Diagram ของระบบ
- [ ] กำหนดขอบเขต Web/API, Profiling Engine, AI Service, Specification Engine, Code Generator และ Validation Sandbox
- [ ] ออกแบบ Project domain model
- [ ] ออกแบบ Source Configuration model
- [ ] ออกแบบ Field Profile และ Schema model
- [ ] ออกแบบ Transformation Rule model
- [ ] ออกแบบ Pipeline Specification กลางที่ไม่ผูกกับภาษา
- [ ] ออกแบบ Validation Rule และ Error Policy
- [ ] ออกแบบ Generated Artifact และ Version model
- [ ] กำหนด lifecycle/status ของ Project และ Generation Job
- [ ] จัดทำ JSON Schema หรือ Pydantic model สำหรับ Pipeline Specification
- [ ] กำหนด versioning และ backward compatibility ของ Specification
- [ ] กำหนด interface สำหรับ Source Connector
- [ ] กำหนด interface สำหรับ Code Generator แต่ละภาษา
- [ ] กำหนด Capability Matrix ของ Python, SQL และ JavaScript
- [ ] ออกแบบโครงสร้างฐานข้อมูลของระบบ
- [ ] ออกแบบ API contract และ error response มาตรฐาน
- [ ] จัดทำ Architecture Decision Records สำหรับการตัดสินใจสำคัญ

- [ ] กำหนด output contract: destination/format ที่รองรับ, schema, encoding, null representation และ configuration ที่จำเป็น
- [ ] กำหนด overwrite/append policy, atomic write หรือ cleanup เมื่อเขียนไม่ครบ และพฤติกรรมเมื่อ run ซ้ำ
- [ ] กำหนด transformation semantics สำหรับ null, decimal precision, timezone, locale, sort stability, deduplication และ rule ordering
- [ ] ออกแบบ source aliases และ Join contract สำหรับ scope ที่อนุมัติ รวม join keys/types, cardinality และ duplicate-column handling
- [ ] ออกแบบ job execution: queue/scheduler, worker lifecycle, concurrency/backpressure, retry policy และ crash recovery
- [ ] กำหนด immutable revision/source fingerprint และ dependency invalidation ของ confirmation, preview, validation และ artifacts
- [ ] จัดทำ threat model และกำหนด project ownership, connector network policy และ sandbox filesystem/process/network boundaries

### Phase 2 Exit Criteria

- [ ] Architecture contracts ข้างต้นได้รับการ review และมี mapping ไปยัง implementation tasks
- [ ] Pipeline Specification ผ่านการ review
- [ ] API และ component boundaries ชัดเจนเพียงพอสำหรับเริ่ม implementation
- [ ] มี automated validation สำหรับ Specification

---

## Phase 3 — Local Llama Evaluation and AI Foundation

- [ ] สำรวจ Local Llama models ที่มีอยู่ในเครื่อง
- [ ] บันทึก model name, parameter size, quantization, context length, file format และ license
- [ ] ตรวจสอบทรัพยากรเครื่อง ได้แก่ CPU, RAM, GPU และ VRAM
- [ ] เลือก inference runtime ที่เหมาะกับ model และ hardware
- [ ] ทดสอบว่า runtime เรียกใช้ได้จาก `ai_env`
- [ ] ออกแบบ AI provider interface เพื่อเปลี่ยน model/runtime ได้โดยไม่กระทบ business logic
- [ ] สร้างชุดตัวอย่างความต้องการภาษาไทยและอังกฤษสำหรับ benchmark
- [ ] กำหนด schema ของ structured output จาก Llama
- [ ] ออกแบบ system prompt สำหรับแปลงภาษาธรรมชาติเป็น Transformation Specification
- [ ] บังคับ validate AI output ด้วย schema ก่อนใช้งาน
- [ ] ป้องกันไม่ให้ข้อมูลต้นทางถูกตีความเป็น system instruction
- [ ] ทดสอบความถูกต้องของ field reference และ transformation rule
- [ ] ทดสอบภาษาไทย ภาษาอังกฤษ และข้อความผสมสองภาษา
- [ ] วัด latency, memory usage และความถูกต้องของแต่ละ local model
- [ ] เลือก Local Llama model เริ่มต้นและบันทึกเหตุผล
- [ ] กำหนด confidence, warning และ clarification behavior เมื่อคำสั่งกำกวม
- [ ] เพิ่ม model/runtime libraries ที่เลือกใน `requirements.txt`
- [ ] เพิ่มการตั้งค่า model path ผ่าน configuration โดยไม่ hard-code path
- [ ] หาก local model ไม่ผ่านเกณฑ์ ให้กำหนดเกณฑ์ค้นหาโมเดลทดแทนจาก Hugging Face
- [ ] ตรวจสอบ license, model card, file size และ hardware compatibility ก่อนดาวน์โหลดจาก Hugging Face
- [ ] ดาวน์โหลดและ cache โมเดลเพิ่มเฉพาะเมื่อได้รับการประเมินว่าจำเป็น
- [ ] จัดทำ Model Evaluation Report และ Model Usage Guide

### Phase 3 Exit Criteria

- [ ] Local Llama สร้าง structured output ที่ผ่าน schema validation ได้
- [ ] โมเดลผ่านเกณฑ์ benchmark ที่กำหนด
- [ ] มี fallback behavior เมื่อ model โหลดไม่ได้หรือผลลัพธ์ไม่ถูกต้อง
- [ ] ไม่มี sample data หรือ secret รั่วไหลผ่าน prompt/log

---

## Phase 4 — Project, Authentication, and Persistence Foundation

- [ ] พัฒนา Project CRUD
- [ ] พัฒนา Project status workflow
- [ ] จัดเก็บ Source Configuration โดยไม่เก็บ secret แบบ plain text
- [ ] จัดเก็บ Pipeline Specification และ version history
- [ ] จัดเก็บ generation job และ validation result
- [ ] เพิ่ม created/updated timestamp และผู้ดำเนินการ
- [ ] พัฒนา authentication ขั้นพื้นฐาน
- [ ] พัฒนา role-based access control
- [ ] เพิ่ม audit events สำหรับ upload, analyze, confirm, generate, execute และ download
- [ ] พัฒนา API validation และมาตรฐาน error response
- [ ] เขียน unit tests สำหรับ domain และ persistence layer
- [ ] เขียน API integration tests

- [ ] พัฒนา database migrations พร้อมทดสอบการติดตั้งใหม่ การ upgrade และ recovery เมื่อ migration ล้มเหลว
- [ ] พัฒนา job queue/worker, progress reporting, concurrency limits และ bounded retries ตาม error policy
- [ ] ป้องกัน duplicate submission และกำหนด cancellation, interrupted-job recovery และ cleanup หลัง worker crash
- [ ] ผูก job/result/artifact กับ source fingerprint, confirmed schema และ specification revision ที่ใช้จริง
- [ ] เมื่อ source/schema/rules เปลี่ยน ให้ invalidate ผลที่เกี่ยวข้องและบังคับ reconfirm ก่อน generation
- [ ] ป้องกันผลจาก job เก่าเขียนทับ revision ใหม่ และทดสอบ simultaneous edits/job completion
- [ ] บังคับ project ownership และ resource-level authorization สำหรับ samples, jobs, versions และ artifact downloads

### Phase 4 Exit Criteria

- [ ] Migration, job recovery, revision invalidation และ cross-user access tests ผ่าน
- [ ] ผู้ใช้สร้าง เปิด แก้ไข และบันทึก Project ได้
- [ ] Specification version สามารถเรียกดูย้อนหลังได้
- [ ] สิทธิ์และ audit log ผ่านการทดสอบพื้นฐาน

---

## Phase 5 — File Source Ingestion

- [ ] พัฒนา upload flow และ file validation
- [ ] รองรับ CSV
- [ ] รองรับ JSON
- [ ] รองรับ JSON Lines
- [ ] รองรับ Microsoft Excel และการเลือก Sheet
- [ ] รองรับ Parquet
- [ ] รองรับ delimiter และ encoding configuration สำหรับ CSV
- [ ] ตรวจสอบ MIME type, extension และ file signature
- [ ] กำหนดและบังคับ file size limit
- [ ] ป้องกัน path traversal และ unsafe archive/file handling
- [ ] จำกัดจำนวน row/column ที่ใช้วิเคราะห์
- [ ] จัดเก็บ temporary file อย่างปลอดภัย
- [ ] ลบ temporary file ตาม retention policy
- [ ] สร้าง normalized source metadata
- [ ] เขียน tests สำหรับไฟล์ปกติ ไฟล์เสีย encoding ผิด และ schema ไม่สม่ำเสมอ

### Phase 5 Exit Criteria

- [ ] อ่านทุก file format ในขอบเขต MVP ได้
- [ ] ข้อผิดพลาดแสดงสาเหตุและแนวทางแก้ไขที่ผู้ใช้เข้าใจได้
- [ ] ระบบไม่แก้ไขไฟล์ต้นทางและไม่เก็บไฟล์เกิน retention policy

---

## Phase 6 — Database Source Connectors

- [ ] ออกแบบ connection configuration และ secret reference
- [ ] พัฒนา connection test แบบ read-only
- [ ] รองรับ PostgreSQL
- [ ] รองรับ MySQL
- [ ] รองรับ Microsoft SQL Server
- [ ] รองรับการเลือก schema, table และ view
- [ ] รองรับ custom SELECT query ภายใต้นโยบายความปลอดภัย
- [ ] ตรวจสอบและปฏิเสธ query ที่แก้ไขข้อมูล
- [ ] จำกัดจำนวน row และ timeout ของ sample query
- [ ] Mask credential และ sensitive connection information ใน UI/log
- [ ] รองรับ connection cancellation และ cleanup
- [ ] เขียน connector contract tests
- [ ] เขียน integration tests กับฐานข้อมูลทดสอบ

- [ ] บังคับสิทธิ์ read-only ที่ database account/session และทดสอบ query ที่มี side effects; ไม่อาศัยการตรวจคำว่า SELECT เพียงอย่างเดียว
- [ ] บังคับ connector network/host policy, TLS configuration และป้องกันการเข้าถึง endpoint ที่อยู่นอกสิทธิ์

### Phase 6 Exit Criteria

- [ ] Connector ที่อยู่ใน MVP ดึง sample แบบ read-only ได้
- [ ] ระบบไม่แสดงหรือบันทึก password/token แบบ plain text
- [ ] Query limit และ timeout ทำงานตามข้อกำหนด

---

## Phase 7 — Schema Inference and Data Profiling

- [ ] พัฒนา schema inference
- [ ] ตรวจหา string, integer, decimal, boolean, date, datetime และ null
- [ ] ตรวจหา mixed data types
- [ ] ตรวจหา date/time format
- [ ] คำนวณ null count และ null percentage
- [ ] คำนวณ distinct count
- [ ] คำนวณ min/max สำหรับ field ที่เหมาะสม
- [ ] แสดง sample values ตามนโยบาย masking
- [ ] คำนวณ confidence ของ inferred type
- [ ] พัฒนา PII/sensitive-data detection เบื้องต้น
- [ ] รองรับการ override data type โดยผู้ใช้
- [ ] แยก inferred schema กับ user-confirmed schema
- [ ] จัดการข้อมูลจำนวนมากแบบ sampling
- [ ] เขียน tests สำหรับ edge cases และข้อมูลหลายภาษา
- [ ] สร้าง profiling result API

### Phase 7 Exit Criteria

- [ ] Profiling แสดงข้อมูลตาม PRD ครบ
- [ ] ผู้ใช้แก้ไขและยืนยัน schema ได้
- [ ] ค่า sensitive ถูก mask ตาม policy

---

## Phase 8 — Requirement Interpretation and Specification Builder

- [ ] สร้างหน้าหรือ API รับความต้องการภาษาไทยและอังกฤษ
- [ ] เชื่อม Local Llama เข้ากับ AI provider interface
- [ ] ส่งเฉพาะ schema/context ที่จำเป็นให้ model
- [ ] แปลงความต้องการเป็น structured transformation rules
- [ ] Validate field references กับ confirmed schema
- [ ] ตรวจหา field ที่ไม่มีอยู่และ rule ที่ไม่รองรับ
- [ ] สร้าง clarification questions เมื่อ requirement กำกวม
- [ ] แสดง assumptions และ warnings
- [ ] รองรับ Include/Exclude
- [ ] รองรับ Rename
- [ ] รองรับ Type Casting
- [ ] รองรับ Filter และ Sort
- [ ] รองรับ Deduplicate
- [ ] รองรับ Replace Value และ Null Handling
- [ ] รองรับ Derived Field
- [ ] รองรับ Aggregate
- [ ] รองรับ Join ตามขอบเขตที่อนุมัติ
- [ ] รองรับ Data Validation Rule
- [ ] รองรับ Sensitive Data Masking Rule
- [ ] ให้ผู้ใช้เพิ่ม แก้ไข ลบ และจัดลำดับ rule
- [ ] บันทึก confirmed specification แยกจาก AI suggestion
- [ ] บังคับ user confirmation ก่อน code generation
- [ ] เขียน tests สำหรับ prompt, structured output และ invalid rules

- [ ] พัฒนา output configuration และ validate กับ output contract/capability ของ target language
- [ ] หาก Join อยู่ใน MVP ให้รองรับหลาย source พร้อม aliases, keys/types และตรวจ ambiguous field/cardinality ตาม contract
- [ ] หาก Join ไม่อยู่ใน MVP ให้ระบุ Deferred ใน Scope Matrix และปฏิเสธคำขอพร้อมคำอธิบาย

### Phase 8 Exit Criteria

- [ ] ความต้องการตัวอย่างใน benchmark ถูกแปลงเป็น Specification ได้ตามเกณฑ์
- [ ] AI output ที่ผิด schema ไม่เข้าสู่ code generation
- [ ] ผู้ใช้เห็นและยืนยัน assumptions/rules ก่อนดำเนินการต่อ

---

## Phase 9 — Transformation Preview and Validation Engine

- [ ] พัฒนา transformation executor สำหรับ sample data
- [ ] แสดง before/after preview
- [ ] แสดง input/output/rejected record counts
- [ ] แสดงผลกระทบของแต่ละ rule
- [ ] แสดง validation errors และ warnings แยกกัน
- [ ] รองรับ rejected-record preview โดย mask sensitive data
- [ ] ตรวจจับ schema change และผลกระทบต่อ rule เดิม
- [ ] เพิ่ม timeout, memory limit และ cancellation
- [ ] แยก execution workspace ต่อ job
- [ ] ปิด network access สำหรับ sandbox โดยค่าเริ่มต้น
- [ ] ลบ temporary execution data หลังจบงาน
- [ ] เขียน tests สำหรับ transformation ทุกประเภท
- [ ] เขียน tests สำหรับ resource limit และ malicious input

- [ ] ใช้ transformation semantics ที่กำหนดร่วมกันและสร้าง shared expected-output fixtures สำหรับทุก MVP rule
- [ ] ทดสอบ Join ด้วยหลาย source หากอยู่ใน MVP รวม null keys, duplicate keys และ duplicate column names
- [ ] บังคับ sandbox filesystem/process isolation, execution identity และ CPU/process/output-size limits ตาม threat model
- [ ] ทดสอบ cancellation และ cleanup ทั้งกรณีสำเร็จ ล้มเหลว timeout และ process crash

### Phase 9 Exit Criteria

- [ ] Preview ตรงกับ confirmed specification
- [ ] Validation status แยก Generated, Syntax Validated และ Sample Tested อย่างถูกต้อง
- [ ] Sandbox ไม่เข้าถึง resource ที่ไม่ได้รับอนุญาต

---

## Phase 10 — Python Code Generator

- [ ] ออกแบบ Python generator templates
- [ ] สร้าง code สำหรับ file input
- [ ] สร้าง code สำหรับ database input
- [ ] สร้าง code สำหรับ field selection และ rename
- [ ] สร้าง code สำหรับ type conversion
- [ ] สร้าง code สำหรับ filter, sort และ deduplicate
- [ ] สร้าง code สำหรับ null handling และ value replacement
- [ ] สร้าง code สำหรับ derived fields และ aggregation
- [ ] สร้าง code สำหรับ validation และ rejected records
- [ ] สร้าง configuration และ environment variable handling
- [ ] สร้าง logging และ error handling
- [ ] สร้าง output writer ตาม format ที่รองรับ
- [ ] สร้าง `requirements.txt` สำหรับ generated package
- [ ] สร้าง unit tests สำหรับ generated pipeline
- [ ] ตรวจ syntax และ format generated Python
- [ ] Execute generated code กับ sample data ใน sandbox
- [ ] สร้าง golden tests สำหรับ generator

- [ ] สร้าง Join และ sensitive-data masking code ตาม Capability Matrix หรือ reject ก่อน generation หากไม่รองรับ
- [ ] ใช้ output contract รวม partial-write cleanup และ overwrite/append policy พร้อมทดสอบ run ซ้ำ

### Phase 10 Exit Criteria

- [ ] เปรียบเทียบผล Python กับ shared fixtures/preview สำหรับทุก MVP transformation และ rule combinations ที่สำคัญ
- [ ] Generated Python ผ่าน syntax check
- [ ] Generated Python ให้ผลลัพธ์ตรงกับ preview
- [ ] ไม่มี credential หรือ machine-specific path ฝังอยู่ใน code

---

## Phase 11 — SQL Code Generator

- [ ] ออกแบบ SQL generator templates
- [ ] กำหนด dialect abstraction
- [ ] รองรับ PostgreSQL dialect
- [ ] รองรับ MySQL dialect
- [ ] รองรับ Microsoft SQL Server dialect
- [ ] Generate SELECT, alias, cast, filter, sort และ deduplicate
- [ ] Generate derived fields และ aggregation
- [ ] Generate validation queries
- [ ] Quote identifier และ parameterize values อย่างปลอดภัย
- [ ] ปฏิเสธ unsupported transformation พร้อมคำอธิบาย
- [ ] ตรวจ syntax ตาม dialect
- [ ] Execute SQL กับ test database เมื่อทำได้
- [ ] สร้าง golden tests แยกตาม dialect

- [ ] ระบุ SQL input/output boundary ให้ชัดเจน รวมข้อจำกัดของ file sources และวิธีส่งคืน query results
- [ ] Generate Join, null handling, value replacement และ masking ตาม Capability Matrix หรือ reject ก่อน generation

### Phase 11 Exit Criteria

- [ ] เปรียบเทียบผลกับ shared fixtures/preview บนทุก MVP dialect; syntax-only validation ไม่ถือเป็น Sample Tested
- [ ] Generated SQL ผ่าน dialect validation
- [ ] SQL ไม่มีคำสั่งแก้ไข source data โดยไม่ได้รับอนุญาต
- [ ] ผลลัพธ์ตรงกับ Specification และ preview

---

## Phase 12 — JavaScript/Node.js Code Generator

- [ ] ออกแบบ JavaScript generator templates
- [ ] สร้าง code สำหรับ file input
- [ ] สร้าง code สำหรับ database input ตาม connector ที่รองรับ
- [ ] สร้าง transformation functions ตาม Capability Matrix
- [ ] รองรับ validation, logging และ error handling
- [ ] สร้าง configuration และ environment variable handling
- [ ] สร้าง `package.json` และ dependency versions
- [ ] สร้าง unit tests สำหรับ generated pipeline
- [ ] ตรวจ syntax และ format generated JavaScript
- [ ] Execute generated code กับ sample data ใน sandbox
- [ ] สร้าง golden tests สำหรับ generator

- [ ] สร้าง output writer ตาม output contract รวม partial-write cleanup และ overwrite/append policy
- [ ] รองรับ Join และ masking ตาม Capability Matrix หรือ reject ก่อน generation

### Phase 12 Exit Criteria

- [ ] เปรียบเทียบผล JavaScript กับ shared fixtures/preview รวม decimal, timezone และ null edge cases
- [ ] Generated JavaScript ผ่าน syntax check
- [ ] Generated JavaScript ให้ผลลัพธ์ตรงกับ preview
- [ ] Unsupported rules ถูกแจ้งก่อน generation

---

## Phase 13 — README and Export Package Generation

- [ ] สร้าง README template
- [ ] สร้างภาพรวม Pipeline จาก Specification
- [ ] ระบุ input/output schema
- [ ] ระบุ transformation และ validation rules
- [ ] ระบุ prerequisites และ dependency installation
- [ ] ระบุ environment variables โดยไม่เปิดเผยค่า secret
- [ ] สร้าง run commands ที่ตรงกับ generated files
- [ ] เพิ่ม assumptions, warnings และ known limitations
- [ ] เพิ่ม security notes และ troubleshooting
- [ ] เพิ่มจุดเชื่อมต่อกับขั้นตอนถัดไป
- [ ] สร้าง `.env.example`
- [ ] Export Specification เป็น JSON หรือ YAML
- [ ] สร้าง sample output ที่ผ่าน masking
- [ ] สร้าง ZIP package
- [ ] ตรวจว่า package ไม่มี source sample หรือ credential โดยค่าเริ่มต้น
- [ ] แสดงรายการไฟล์และ validation status ก่อนดาวน์โหลด
- [ ] ทดสอบติดตั้งและ run generated package ใน clean environment

- [ ] แนบ artifact manifest ระบุ source/schema/specification revision, generator/model version และ validation evidence โดยไม่เปิดเผย secrets
- [ ] แสดงสถานะ stale เมื่อ package ไม่ตรงกับ revision ปัจจุบัน และแยกการดาวน์โหลด historical version ให้ชัดเจน

### Phase 13 Exit Criteria

- [ ] ZIP มี source, tests, config example, README และ Specification ครบ
- [ ] คำสั่งใน README ใช้งานได้จริง
- [ ] Secret scan ของ package ผ่าน

---

## Phase 14 — Production UI Integration and End-to-End Hardening

- [ ] ทบทวน Early Test UI feedback และยืนยัน production information architecture
- [ ] เปลี่ยน Project Dashboard จาก mock เป็น persistence/API จริง
- [ ] เชื่อม Source Input กับ file upload และ database connection APIs จริง
- [ ] เชื่อม Schema Analysis และ Confirmation กับ profiling APIs จริง
- [ ] เชื่อม Requirement Input กับ Local Llama และ clarification flow จริง
- [ ] เชื่อม Field Mapping และ Rule Editor กับ versioned Pipeline Specification
- [ ] เชื่อม Before/After Preview กับ sandbox validation engine
- [ ] เชื่อม language/dialect/runtime selection กับ Capability Matrix
- [ ] เชื่อม Code, README, manifest และ Export กับ generated artifacts จริง
- [ ] ลบหรือปิด mock/stub ทั้งหมดจาก production configuration
- [ ] รองรับ loading, empty, error, retry และ partial-failure states จาก API จริง
- [ ] รองรับการย้อนกลับไปแก้ไขขั้นก่อนหน้าโดยรักษา revision consistency
- [ ] แสดง job progress, cancellation และ recovery หลัง reload/reconnect โดยไม่สร้าง job ซ้ำ
- [ ] เมื่อแก้ source/schema/rules ให้แสดง stale results และขั้นตอนที่ต้องยืนยันหรือประมวลผลใหม่
- [ ] ทดสอบ keyboard navigation, responsive layout และ accessibility ขั้นพื้นฐาน
- [ ] เขียน end-to-end tests สำหรับ happy path ของ vertical slice จริง
- [ ] เขียน end-to-end tests สำหรับ failure, authorization และ recovery paths
- [ ] พัฒนาและทดสอบ vertical slice จริง: CSV → profiling → confirm → preview → Python → ZIP export

### Phase 14 Exit Criteria

- [ ] ทดสอบ stale-result handling และ authorization ใน user journeys ที่เกี่ยวข้อง
- [ ] ผู้ใช้ทำ workflow ตั้งแต่สร้าง Project ถึงดาวน์โหลด package ได้
- [ ] UI แยก inferred, suggested และ user-confirmed values ชัดเจน
- [ ] Critical user journeys ผ่าน end-to-end tests

---

## Phase 15 — Security, Privacy, and Compliance Hardening

- [ ] ทบทวนและปรับปรุง threat model ที่จัดทำไว้ใน Phase 2 ให้สอดคล้องกับ implementation จริง
- [ ] Review file upload attack surface
- [ ] Review database connector และ query attack surface
- [ ] Review prompt injection และ model output attack surface
- [ ] Review generated code execution sandbox
- [ ] เพิ่ม secret scanning สำหรับ source และ generated artifacts
- [ ] เพิ่ม dependency vulnerability scanning
- [ ] เพิ่ม authentication/authorization tests
- [ ] ตรวจสอบ encryption in transit และ at rest
- [ ] ตรวจสอบ data retention และ deletion flow
- [ ] ตรวจสอบ PII masking และ log redaction
- [ ] เพิ่ม rate limiting และ abuse protection
- [ ] เพิ่ม security headers และ secure configuration defaults
- [ ] ทดสอบการลบ Project, sample data และ generated artifacts
- [ ] จัดทำ Security and Privacy Checklist ก่อน release

- [ ] ทดสอบ cross-user access denial สำหรับ project, samples, jobs, artifacts, versions และ download URLs
- [ ] ทดสอบ session expiry/logout และ permission changes ว่าไม่เปิดสิทธิ์เข้าถึง resource ต่อโดยไม่ตั้งใจ
- [ ] ทดสอบ sandbox escape attempts, filesystem/process restrictions และ connector network policy ตาม threat model

### Phase 15 Exit Criteria

- [ ] ไม่มี Critical หรือ High severity issue ที่ยังไม่ได้รับการแก้ไข
- [ ] Data deletion และ retention policy ผ่านการทดสอบ
- [ ] Security checklist ได้รับการอนุมัติ

---

## Phase 16 — Quality Assurance and Performance Testing

- [ ] ตรวจ test coverage และเติม test ในส่วนสำคัญ
- [ ] ทดสอบทุก supported file format
- [ ] ทดสอบทุก database connector
- [ ] ทดสอบทุก transformation rule
- [ ] ทดสอบทุก code generator และ dialect
- [ ] ทดสอบภาษาไทย อังกฤษ และข้อความผสม
- [ ] ทดสอบ corrupted, malformed และ adversarial input
- [ ] ทดสอบ concurrency ของ generation jobs
- [ ] ทดสอบ file size และ row limits
- [ ] ทดสอบ profiling performance
- [ ] ทดสอบ AI latency และ memory usage
- [ ] ทดสอบ code generation และ sandbox performance
- [ ] ทดสอบ generated packages ใน clean environments
- [ ] แก้ไข defect ตาม severity
- [ ] จัดทำ QA report และ release recommendation

- [ ] รัน cross-generator parity suite จาก shared fixtures ครบทุก MVP language/dialect และตรวจค่ากับ data types ตาม contract
- [ ] ทดสอบ queue saturation, duplicate submission, worker crash, cancellation และ recovery ภายใต้ concurrency ที่กำหนด
- [ ] ทดสอบ output failures, repeated runs และ stale revisions ไม่ให้เกิดไฟล์ไม่สมบูรณ์หรือผลที่อ้างอิงผิด version

### Phase 16 Exit Criteria

- [ ] Requirements Traceability Matrix มีหลักฐานผลผ่านสำหรับทุก MVP requirement; Deferred items แยกชัดเจน
- [ ] Functional acceptance criteria ของ MVP ผ่าน
- [ ] Performance อยู่ในเกณฑ์ที่กำหนด
- [ ] ไม่มี Critical หรือ High severity defect ที่ยังไม่ได้แก้ไข

---

## Phase 17 — Documentation, Pilot, and MVP Release

- [ ] จัดทำ User Guide
- [ ] จัดทำ Developer Guide
- [ ] จัดทำ API Documentation
- [ ] จัดทำ Model Setup and Troubleshooting Guide
- [ ] จัดทำ Supported Sources and Transformations Matrix
- [ ] จัดทำ Deployment and Operations Guide
- [ ] จัดทำ Backup and Recovery Procedure
- [ ] กำหนด monitoring, metrics และ alerting
- [ ] เตรียม pilot users และตัวอย่าง use cases
- [ ] ฝึกอบรม pilot users
- [ ] เก็บ feedback และ usability issues
- [ ] แก้ไข blocker จาก pilot
- [ ] จัดทำ release notes
- [ ] สร้าง release candidate
- [ ] ทำ Go/No-Go review
- [ ] Release MVP
- [ ] เฝ้าระวัง error, latency และ resource usage หลัง release
- [ ] สรุปผลเทียบกับ Success Metrics ใน PRD

- [ ] สร้าง deployment configuration และ versioned build/release artifacts ของตัว PAE พร้อม environment/secrets configuration
- [ ] ตั้งค่า release pipeline ของ PAE พร้อม smoke tests และขั้นตอน rollback ที่ทดสอบแล้ว
- [ ] พัฒนา health/readiness checks ครอบคลุม application, persistence, workers และ model availability ตามหน้าที่ของ service
- [ ] ติดตั้ง structured logs, metrics และ alerts สำหรับ failures, latency, queue depth และ resource usage พร้อมทดสอบ alert delivery
- [ ] ตั้งค่า backup สำหรับ persistent data/configuration ที่จำเป็น และทดสอบ restore ใน environment แยก
- [ ] กำหนด recovery objectives, ผู้รับผิดชอบ incident และ runbooks; บันทึกผล restore/rollback drill
- [ ] ทดสอบ deployment จาก environment สะอาดและ upgrade จาก release ก่อนหน้าเมื่อมี

### Phase 17 Exit Criteria

- [ ] Deployment smoke tests, monitoring, backup restore และ rollback ผ่านก่อน Go/No-Go
- [ ] ผู้ใช้กลุ่ม pilot ทำงานหลักได้โดยไม่มีผู้พัฒนาช่วย
- [ ] Operations สามารถติดตามและแก้ปัญหาพื้นฐานได้
- [ ] MVP ผ่าน Go/No-Go review และเปิดใช้งานแล้ว

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
