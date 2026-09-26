# Definition of Ready

งานพร้อมเข้าสู่ implementation เมื่อ:

- มี Requirement ID หรือระบุชัดว่าเป็น technical enabler ของ requirement ใด
- ระบุว่าเป็น `MVP Required` หรือ `Deferred`
- Acceptance criteria วัดผลได้และมี test approach
- Dependency และ prerequisite ถูกระบุ
- Data/security impact ได้รับการประเมิน
- UX/API/schema contract ที่จำเป็นพร้อมให้ implement
- ไม่มี open question ที่ทำให้ implementation หลักเปลี่ยนทิศทาง
- มี owner และ reviewer
- หากเพิ่ม dependency ต้องมีเหตุผล, license compatibility และ version ใน `requirements.txt`
- หากเกี่ยวกับ AI model ต้องมี benchmark case และ structured-output contract

งานที่ยังไม่ผ่านทุกข้อสามารถทำ discovery/prototype ได้ แต่ห้ามถือว่า implementation พร้อมปิด
