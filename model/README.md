# model/ — pipeline OCR

รายละเอียดทั้งหมดดูที่ [../docs/STRUCTURE.md](../docs/STRUCTURE.md) หัวข้อ 5 · สรุปสั้น:

- ไฟล์ `.py` ในโฟลเดอร์นี้ (`extract.py`, `validate.py`, `photo_geometry.py` ฯลฯ) คือ **pipeline ที่ backend ใช้จริง** อย่าย้ายหรือเปลี่ยนชื่อ
- `tools/` สคริปต์วัดผล/ฝึก/วัดเวลา รันจากโฟลเดอร์รากของ repo: `python -m model.tools.benchmark --help`
- `tests/` unit test รันจากโฟลเดอร์รากด้วย `python -m pytest model backend`
- `data/` manifest การแบ่งชุด, catalog รายวิชา, ไฟล์โมเดล Tesseract ที่ฝึกเพิ่ม
- `reports/`, `runs/` ผลทดสอบที่สคริปต์ใน `tools/` สร้างไว้
