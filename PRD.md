# Product Requirements Document — Pipeline Auto Extraction (PAE)

| รายการ | ค่า |
|---|---|
| สถานะ | Approved baseline |
| เวอร์ชัน | 0.1.0 |
| วันที่ | 2026-09-26 |
| เจ้าของผลิตภัณฑ์ | รอแต่งตั้ง |
| Template อ้างอิง | https://documentero.com/templates/project-management/document/product-requirements-document/ |

## 1. Product Summary

PAE ช่วยผู้ใช้เปลี่ยนตัวอย่างข้อมูลและความต้องการทางธุรกิจให้เป็น Data Pipeline ที่ตรวจสอบได้ ระบบรับข้อมูลจากไฟล์หรือฐานข้อมูล วิเคราะห์ schema และคุณภาพข้อมูล ให้ผู้ใช้ยืนยัน field และ transformation แล้วสร้าง source code, tests, README และตัวอย่างการนำผลลัพธ์ไปใช้ต่อ

หลักการสำคัญคือระบบเสนอและผู้ใช้ยืนยัน โดย Pipeline Specification ที่ยืนยันแล้วเป็นแหล่งอ้างอิงหลักสำหรับ preview, validation และ code generation ทุกภาษา

## 2. Objectives

- ลดเวลาเตรียม Data Pipeline draft อย่างน้อย 50% เมื่อเทียบกับ baseline ที่ตกลงร่วมกัน
- ทำให้ transformation rules ตรวจสอบและย้อนกลับไปยัง requirement ได้
- สร้าง code ที่ผ่าน syntax validation 100% และผลลัพธ์ตรงกับ preview ตาม acceptance suite
- ป้องกัน credential และ sensitive sample data ตลอด workflow
- ทำให้ผู้ใช้ตั้งแต่ Business Analyst ถึง Data Engineer ทำงานร่วมกันบน specification เดียวกัน

## 3. Users

- Business Analyst ระบุผลลัพธ์และยืนยัน business rules
- Data Analyst สำรวจ schema และ data quality
- Data Engineer ตรวจสอบ specification, generated code และ operational constraints
- Developer นำ package ไปพัฒนาหรือ integrate ต่อ
- Product Owner อนุมัติ scope และ acceptance criteria
- Security/Compliance ตรวจสอบการจัดการข้อมูลและ credentials

## 4. Core Workflow

1. สร้าง Project
2. อัปโหลดไฟล์ตัวอย่างหรือเชื่อมต่อฐานข้อมูลแบบ read-only
3. วิเคราะห์ schema, data types, nulls, distinct values, ranges และ sensitive data
4. ผู้ใช้แก้ไขและยืนยัน schema
5. ผู้ใช้อธิบายผลลัพธ์ที่ต้องการเป็นภาษาไทยหรืออังกฤษ
6. Local Llama แปลงคำอธิบายเป็น structured transformation rules
7. ผู้ใช้แก้ไขและยืนยัน Pipeline Specification
8. ระบบสร้างและแสดง preview บน sample data
9. ผู้ใช้เลือก Python, SQL หรือ JavaScript/Node.js ตาม capability ที่รองรับ
10. ระบบสร้าง code, tests, configuration, README และ manifest
11. ระบบตรวจ syntax และทดลองกับ sample ใน sandbox
12. ผู้ใช้ดาวน์โหลด ZIP package

## 5. Functional Requirements

| ID | Requirement | Priority |
|---|---|---|
| PAE-FR-001 | สร้าง เปิด แก้ไข และเก็บ version ของ Project | Must |
| PAE-FR-002 | รับ CSV, JSON, JSON Lines, Excel และ Parquet ตาม Scope Matrix | Must |
| PAE-FR-003 | เชื่อม PostgreSQL, MySQL และ SQL Server แบบ read-only ตาม Scope Matrix | Must |
| PAE-FR-004 | วิเคราะห์ schema และ data profile จาก sample โดยไม่แก้ไข source | Must |
| PAE-FR-005 | ตรวจหาและ mask sensitive sample values ตาม policy | Must |
| PAE-FR-006 | ให้ผู้ใช้แก้ไขและยืนยัน inferred schema | Must |
| PAE-FR-007 | รับ requirement ภาษาไทยและอังกฤษ | Must |
| PAE-FR-008 | ใช้ Local Llama แปลง requirement เป็น structured rules ที่ผ่าน schema validation | Must |
| PAE-FR-009 | แสดง clarification, assumption และ warning เมื่อ requirement กำกวม | Must |
| PAE-FR-010 | รองรับ transformation ตาม Scope Matrix และปฏิเสธ capability ที่ไม่รองรับก่อน generation | Must |
| PAE-FR-011 | บังคับ user confirmation ก่อน preview และ code generation | Must |
| PAE-FR-012 | แสดง before/after preview, counts, warnings และ rejected records | Must |
| PAE-FR-013 | สร้าง Python code ที่ให้ผลตรงกับ shared transformation semantics | Must |
| PAE-FR-014 | สร้าง SQL ตาม dialect และ capability ที่อนุมัติ | Must |
| PAE-FR-015 | สร้าง JavaScript/Node.js ตาม capability ที่อนุมัติ | Must |
| PAE-FR-016 | สร้าง README, tests, config example, specification และ artifact manifest | Must |
| PAE-FR-017 | ตรวจ syntax และ sample execution ใน isolated sandbox | Must |
| PAE-FR-018 | Export package โดยไม่มี credential หรือ raw sample โดยค่าเริ่มต้น | Must |
| PAE-FR-019 | ผูกผลลัพธ์กับ source fingerprint, schema และ specification revision | Must |
| PAE-FR-020 | บันทึก audit events ของการกระทำสำคัญ | Must |
| PAE-FR-021 | Generated file pipeline ต้องเป็น script เต็มที่ค้นหาและประมวลผลไฟล์อนาคตใน folder ตาม pattern ด้วย schema/failure/idempotency policy ที่ยืนยันแล้ว | Must |

## 6. Non-functional Requirements

| ID | Requirement |
|---|---|
| PAE-NFR-001 | API health endpoint ตอบภายใน 1 วินาทีในสภาวะปกติ |
| PAE-NFR-002 | Profiling sample ตามขีดจำกัด MVP เสร็จภายในเกณฑ์ที่ระบุใน Acceptance Thresholds |
| PAE-NFR-003 | Generation jobs มี progress, timeout, cancellation, bounded retry และ crash cleanup |
| PAE-NFR-004 | Secrets ไม่ปรากฏใน source, log, preview หรือ exported artifacts |
| PAE-NFR-005 | Sample และ temporary files ถูกลบตาม retention policy |
| PAE-NFR-006 | Resource ทุกชนิดถูกตรวจ project ownership และ authorization |
| PAE-NFR-007 | Sandbox จำกัด filesystem, process, CPU, memory, output size และ network |
| PAE-NFR-008 | Generated output ระหว่าง preview และทุก generator ผ่าน shared fixtures เดียวกัน |
| PAE-NFR-009 | รองรับ Windows development ผ่าน conda env `ai_env` และ Python 3.11 |
| PAE-NFR-010 | CI ต้องผ่าน lint, formatting, type checking, tests และ security checks ที่กำหนด |
| PAE-NFR-011 | การรัน folder batch ซ้ำด้วยไฟล์เดิมและ state เดิมต้องไม่สร้างผลลัพธ์ซ้ำ |

## 7. Assumptions

- ระบบเริ่มจาก local/on-premise deployment และออกแบบไม่ผูกกับ deployment target
- ผู้ใช้มีสิทธิ์นำ sample data เข้าสู่ระบบ
- Database credentials ของ MVP ใช้บัญชี read-only และไม่ถูกเก็บแบบ plain text
- Local Llama เป็นค่าเริ่มต้น; ดาวน์โหลดจาก Hugging Face เมื่อ local model ไม่ผ่าน benchmark และ license review
- Generated code ต้องผ่าน human review ก่อนใช้ใน production
- File pipeline ทำงานแบบ scan-on-run; scheduling หรือ continuous folder watching เป็นหน้าที่ของ Task Scheduler, cron หรือ orchestrator ภายนอก
- ค่าที่มีผลต่อ scope และ security ใน `docs/OPEN_QUESTIONS.md` ยังต้องได้รับ stakeholder approval

## 8. Constraints

- Sample อาจไม่ครอบคลุม edge cases ของข้อมูลจริง
- SQL dialect และ transformation capability แตกต่างกัน
- คุณภาพ AI output ขึ้นกับ model, context และความชัดเจนของ requirement
- Hardware ของเครื่องเป้าหมายจำกัดขนาดและ latency ของ Local Llama
- Sample validation ไม่เท่ากับ production certification

## 9. Out of Scope for MVP

- Production deployment ของ generated pipeline
- Scheduled execution และ real-time streaming
- Airflow, Dagster, Prefect และ dbt export
- Enterprise data catalog และ end-to-end data lineage
- Custom plugin SDK
- การเขียนกลับไปยัง source database โดยอัตโนมัติ

## 10. Acceptance and Release

- Requirement ที่เป็น MVP ต้อง trace ไปยัง scope, implementation task, acceptance test และ evidence ได้
- Deferred item ไม่ถือเป็นตัวขวาง release เมื่อได้รับอนุมัติและแยกไว้ใน backlog
- ไม่มี Critical หรือ High security defect ก่อน release
- เกณฑ์เชิงตัวเลขอยู่ใน `docs/ACCEPTANCE_THRESHOLDS.md`
- รายละเอียดขอบเขตอยู่ใน `docs/SCOPE_MATRIX.md`
- Traceability อยู่ใน `docs/REQUIREMENTS_TRACEABILITY.md`

## 11. Approval

| Role | Name | Decision | Date |
|---|---|---|---|
| Project Owner | User | Approved baseline | 2026-09-26 |
| Engineering Lead | รอระบุ | Review during implementation | - |
| Security/Compliance | รอระบุ | Review during Phase 2/15 | - |
