# Early UI Testing Strategy

## Purpose

สร้าง Web UI สำหรับทดสอบความเข้าใจและลำดับการใช้งานก่อนที่ backend capabilities ทั้งหมดจะเสร็จ ลดความเสี่ยงที่ระบบทำงานถูกต้องทางเทคนิคแต่ใช้งานยากหรือสื่อสารสถานะไม่ชัดเจน

## Approach

- ใช้ FastAPI เป็น backend และ entry point เดิม
- เลือก server-rendered UI/HTMX เป็นแนวทางเริ่มต้น เพื่อคง Python เป็นแกนหลักและลด build toolchain
- ใช้ synthetic fixtures และ deterministic stubs เท่านั้นใน Early Test UI
- ทุกหน้าต้องแสดง `Prototype / Mock Data` banner เมื่อยังไม่เชื่อม service จริง
- แยก mock provider ออกจาก production interface และเปิดได้เฉพาะ development/testing configuration
- เชื่อม service จริงทีละ capability โดยรักษา UI contract และ automated tests เดิม

## Prototype Flow

1. Project Dashboard
2. Source Input
3. Schema Analysis and Confirmation
4. Requirement Input
5. Field Mapping and Rule Editor
6. Before/After Preview
7. Target Language Selection
8. Code and README Preview
9. Validation Summary
10. Export Summary

## Test Data

- ใช้ CSV สังเคราะห์ที่ไม่มีข้อมูลบุคคลจริง
- ต้องมี null, duplicate, mixed date format และ numeric text เพื่อทดสอบข้อความแจ้งเตือน
- Expected schema, transformation rules และ preview output ต้อง version control ได้

## Usability Checks

- ผู้ทดสอบรู้ว่าส่วนใดเป็นค่าที่ระบบตรวจพบ, AI suggestion และค่าที่ผู้ใช้ยืนยัน
- ผู้ทดสอบย้อนกลับไปแก้ไขขั้นก่อนหน้าได้
- ผู้ทดสอบเข้าใจ error/warning และรู้ว่าต้องแก้อะไร
- ผู้ทดสอบไม่เข้าใจผิดว่า mock validation หรือ generated code พร้อม production
- Workflow หลักทำได้โดยไม่ใช้ command line

## Promotion to Production UI

Mock screen จะเปลี่ยนเป็น production-connected screen เมื่อ API contract, authorization, revision invalidation และ acceptance tests ของ capability นั้นพร้อมแล้ว Phase 14 มีหน้าที่ปิด mock ทั้งหมดและทดสอบ end-to-end กับ services จริง
