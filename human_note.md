Concept for Full-system
- การ apply เอา apache-airflow มาใช้เพื่อให้จัดการง่ายขึ้น

ลำดับการทำงาน
- เลือกโหมด input ที่ต้องการ
    + Raw File: เช่น csv, excel, txt
    + Database: บอกว่าต้องการอ่านจาก table
    + JSON: บอกว่าต้องการอ่านจาก api, json
- ถ้าเลือก Raw File
    + ระบบทำการ extract file ออกมา
    + จากนั้นทำการบอกว่า มี field อะไรบ้าง
    + user ทำการเลือก field ที่ต้องการ พร้อมบอกว่าอยากได้ชื่อ column อะไร, type ไหน
    + AI/system จะทำการ generate mock-up data โดยอิงจาก structure ที่เลือกมาก่อน
    + หลังจากที่ user ยืนยันแล้ว ระบบจะทำการถามว่า อยากได้ output เป็นภาษาอะไร
        + เบื้องต้นเน้นไปที่ Python, NodeJS, SQL
    + จากนั้น AI จะทำการ generate code สำหรับการ extraction แบบสมบูรณ์ให้
        + ตัวแปร INPUT_FILES, OUTPUT sources
