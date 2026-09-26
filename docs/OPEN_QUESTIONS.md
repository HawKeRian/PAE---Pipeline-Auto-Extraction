# Open Questions and Proposed Decisions

Project Owner อนุมัติรายการต่อไปนี้เป็น MVP baseline เมื่อ 2026-09-26 รายละเอียดเชิง implementation ที่ระบุให้ตัดสินใน Phase 2 ยังคงต้องบันทึกเป็น Architecture Decision Record แต่ไม่ถือเป็น Phase 0 blocker

| ID | Question | Proposed decision | Status |
|---|---|---|---|
| OQ-001 | Deployment รูปแบบใด | Local/on-premise, single-node สำหรับ MVP; ออกแบบให้ containerize ได้ภายหลัง | Approved baseline |
| OQ-002 | Python version | Python 3.11 เพื่อรองรับ AI/data ecosystem และยังได้รับการรองรับกว้าง | Adopted for development |
| OQ-003 | File limit | 100 MB ต่อไฟล์สำหรับ MVP | Approved baseline |
| OQ-004 | Profiling sample | สูงสุด 100,000 rows และไม่เกิน file limit | Approved baseline |
| OQ-005 | Database priority | PostgreSQL → MySQL → SQL Server | Approved baseline |
| OQ-006 | Generated languages | Python, SQL และ JavaScript/Node.js อยู่ใน MVP ตาม PRD | Approved baseline |
| OQ-007 | Multi-source Join | Deferred หลัง MVP | Approved baseline |
| OQ-008 | Output destinations | CSV, JSON Lines, Parquet และ SQL result contract; database writes deferred | Approved baseline |
| OQ-009 | Sample retention | ลบ temporary sample ภายใน 24 ชั่วโมงหรือตาม explicit delete ที่เกิดก่อน | Approved baseline; verify in Phase 15 |
| OQ-010 | Authentication | Local development identity ก่อน; production mechanism ต้องตัดสินใน Phase 2 | Approved baseline |
| OQ-011 | Generated tests | สร้าง unit tests และ shared fixture checks พร้อม package | Adopted |
| OQ-012 | Model acquisition | ประเมิน local models ก่อน; Hugging Face download ต้องผ่าน benchmark need, license และ hardware review | Adopted |

## Decisions That Block Architecture or Security

- Production identity provider และ role model
- Secret storage mechanism
- Approved connector hosts/network boundaries
- Data classification และ retention policy
- Deployment topology และ sandbox isolation mechanism

หัวข้อเหล่านี้ไม่ขวางการเริ่ม Phase 1.5/2 แต่ implementation ที่เกี่ยวข้องต้องผ่าน Architecture/Security review ก่อนปิด task
