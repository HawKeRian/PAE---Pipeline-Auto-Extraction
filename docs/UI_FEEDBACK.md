# Early UI Feedback Log

## UI-001 — Suggest columns after reading the file

| Field | Detail |
|---|---|
| Date | 2026-09-26 |
| Source | Project Owner usability review |
| Screen | Source Input → Schema Analysis |
| Feedback | ระบบควรอ่านไฟล์และแนะนำ column ให้ผู้ใช้ก่อนเข้าสู่การเลือก |
| Decision | Accepted |
| Resolution | เปลี่ยน flow เป็น Read file → Profile → Suggest columns with reasons → User confirms |
| Verification | UI smoke test checks suggestion summary, exclude suggestion and recommendation reason |

### Design Rules from This Feedback

- คำแนะนำต้องแสดงเหตุผล ไม่เลือก column แบบกล่องดำ
- แยก `Recommended`, `Review` และ `Exclude`
- ผู้ใช้มีสิทธิ์แก้ไขคำแนะนำทุกข้อก่อนยืนยัน
- Sensitive field ต้องใช้สถานะ `Review` แม้ระบบคิดว่ามีประโยชน์
- Low-value field สามารถถูกแนะนำให้ตัดออก แต่ห้ามถูกลบโดยอัตโนมัติ
