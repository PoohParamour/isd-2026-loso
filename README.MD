# OCR Transcript (สจล.)

โปรเจกต์พัฒนาระบบ OCR สำหรับแปลงข้อมูลเอกสาร Transcript (สจล.) โดยมุ่งเน้นการประมวลผลเอกสารที่หลากหลายและมีความแม่นยำสูง

---

## 🚀 1. วิธีรันระบบ (ตั้งแต่เปิดเครื่อง)

ระบบประกอบด้วย 2 บริการ (หน้าเว็บ Next.js และ API FastAPI + OCR) รันพร้อมกันด้วย Docker Compose คำสั่งเดียว

**สิ่งที่ต้องมี**
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (มี `docker compose` v2) — ทดสอบด้วย Docker 29.1.4 บน macOS (Apple Silicon)
- พอร์ต **3000** และ **8000** ว่าง
- อินเทอร์เน็ตตอน build ครั้งแรก (ดาวน์โหลด Tesseract ภาษาไทย/อังกฤษ, Poppler และแพ็กเกจ npm)

**ขั้นตอน**

```bash
# 1) เปิดโปรแกรม Docker Desktop แล้วรอจนสถานะเป็น Running

# 2) ดาวน์โหลดโค้ด
git clone https://github.com/PoohParamour/isd-2026-loso.git
cd isd-2026-loso

# 3) build และรันทั้งระบบ (ครั้งแรกใช้เวลาหลายนาที)
docker compose up --build
```

4. รอจนข้อความของ backend ขึ้นว่า healthy แล้ว web เริ่มทำงาน แล้วเปิด **http://localhost:3000**
   (ตรวจ API ได้ที่ http://localhost:8000/api/health ควรได้ `"status":"ok"`)
5. เมื่อต้องการหยุด กด `Ctrl+C` ในเทอร์มินัล หรือรัน `docker compose down`

**เปิดเครื่องใหม่หลังจากเคย build แล้ว:** เปิด Docker Desktop → `cd isd-2026-loso` → `docker compose up` (ไม่ต้อง `--build`) ข้อมูลที่บันทึกไว้ยังอยู่ เพราะเก็บใน Docker volume ชื่อ `ocr_data`

**ล้างข้อมูลทั้งหมดและเริ่มใหม่:** `docker compose down -v`

### วิธีใช้งาน
1. หน้า **นำเข้า Transcript** (`/upload`): ลากไฟล์มาวาง/เลือกหลายไฟล์ หรือกด "เปิดกล้องเพื่อถ่ายรูป" — รองรับ PDF, PNG, JPG, TIFF, HEIC ไม่เกิน 20 MB ต่อไฟล์
2. ระบบแสดงผลที่อ่านได้ ช่องสีเหลืองคือจุดที่ระบบสงสัย แก้ในช่องได้เลย ระบบตรวจซ้ำอัตโนมัติ
3. กด **บันทึกผลที่ตรวจแล้ว** เพื่อเก็บลงฐานข้อมูล
4. หน้า **ค้นหาผลการเรียน** (`/search`): ดูรายชื่อนักศึกษาที่บันทึกไว้ คลิกชื่อเพื่อดูรายวิชารายภาค หรือค้นตามรหัสวิชา

> repo ไม่มีไฟล์ transcript ตัวอย่างแนบมา (ข้อมูลทดสอบอยู่นอก git) ให้ใช้ transcript PDF หรือภาพของสถาบันที่มีอยู่ในการทดลองระบบ

### อ่านไฟล์เดียวผ่านบรรทัดคำสั่ง (ไม่ต้องเปิดหน้าเว็บ)
รันใน container ของระบบโดยไม่ต้องติดตั้ง Python หรือ Tesseract เอง ผลลัพธ์เป็น JSON ทาง stdout (ข้อความสถานะของ Docker ไปทาง stderr):

```bash
docker compose run --rm --no-deps -v "$PWD/ไฟล์ของคุณ.pdf:/tmp/in.pdf:ro" backend \
    python -m model.extract /tmp/in.pdf > result.json
```

ตัวเลือกเพิ่มเติม: `--format {bachelor_th,bachelor_en,graduate_th,graduate_en}` (บังคับรูปแบบเอกสาร), `--force-ocr` (บังคับ OCR), `--out ไฟล์.json` (เขียนลงไฟล์ภายใน container) — `Code.py` ที่ราก repo เรียก `model.extract` ตัวเดียวกัน

### แก้ปัญหาเบื้องต้น
| อาการ | วิธีแก้ |
|---|---|
| `port is already allocated` | พอร์ต 3000 หรือ 8000 ถูกใช้อยู่ ปิดโปรแกรมนั้นก่อน หรือเปลี่ยนเลขพอร์ตฝั่งซ้ายใน `docker-compose.yml` (เช่น `"3001:3000"`) |
| `Cannot connect to the Docker daemon` | ยังไม่ได้เปิด Docker Desktop |
| หน้าเว็บขึ้น "เชื่อมต่อบริการ OCR ไม่สำเร็จ" | backend ยังไม่พร้อม รอสักครู่ หรือดู log ด้วย `docker compose logs backend` |
| build ครั้งแรกช้า | ปกติ ต้องดาวน์โหลดและติดตั้ง Tesseract/Poppler/npm ครั้งต่อไปจะเร็วขึ้นจาก cache |
| ถ่ายรูปด้วยกล้องไม่ได้ | เบราว์เซอร์เปิดกล้องสดได้เฉพาะ `localhost` หรือ HTTPS และต้องอนุญาตกล้อง ถ้าไม่ได้จะเปิดตัวเลือกถ่ายภาพของอุปกรณ์แทน |

### โครงสร้างโปรเจกต์
| โฟลเดอร์/ไฟล์ | คืออะไร |
|---|---|
| `web/` | หน้าเว็บ (Next.js 16 + Tailwind CSS 4) |
| `backend/` | API (FastAPI) และฐานข้อมูล SQLite |
| `model/` | pipeline OCR (`extract.py`), ตัวตรวจ (`validate.py`), สคริปต์วัดผล (`benchmark*.py`) และรายงานผล (`reports/`) |
| `Code.py` | จุดเริ่มสำหรับอ่านไฟล์เดียวจากบรรทัดคำสั่ง |
| `process.md` | บันทึกการตัดสินใจและผลทดสอบของโปรเจกต์ |
| `slide.md`, `promt_slide.md`, `slide_assets/` | แผนสไลด์นำเสนอ prompt และภาพหน้าจอ/ภาพประกอบ |

---

## 📌 รายละเอียดโปรเจกต์ (Project Overview)
* **ชุดข้อมูลที่ใช้ (Dataset):**
  * ข้อมูลจำลอง (Synthetic Data)
  * ข้อมูลจำลองที่มีสัญญาณรบกวน (Synthetic & Noise Data)
  * ข้อมูลจริง (Real Data)
* **วิธีการทำ OCR:** ใช้เทคนิคทาง Computer Vision (CV) หรือ Large Language Model OCR (LLM-OCR)
* **ระบบฐานข้อมูล (Database):** ออกแบบ Database เพื่อจัดเก็บโครงสร้างข้อมูลที่ได้จากการทำ OCR อย่างเป็นระบบ
* **เป้าหมายหลัก:** รองรับเอกสาร (Document) ที่มีความหลากหลาย โดยมีเกณฑ์การวัดผลตามระดับความแม่นยำ (ยิ่งความแม่นยำสูง ยิ่งได้คะแนนมาก)

---

## 👥 สมาชิกในกลุ่ม (Team Members)

| ลำดับ | รายชื่อ-นามสกุล | รหัสนักศึกษา | Discord Account |
| :---: | :--- | :---: | :--- |
| 1 | กวีวัฒน์ สานนท์กุลวัฒน์ | 67070005 | lostinmusic__ |
| 2 | ภคพล โพธิวร | 67070124 | peam |
| 3 | ภัทรพล เพ็ชรรัตน์ | 67070127 | PP |

---
