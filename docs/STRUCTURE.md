# โครงสร้างโปรเจกต์ (Project Structure)

ระบบ OCR Transcript (สจล.): อ่านใบแสดงผลการเรียน (PDF/ภาพ) → ข้อมูล JSON → ตรวจและแก้ → บันทึก → ค้นหา
วิธีรันอยู่ใน [../README.MD](../README.MD) ข้อ 1 · ไฟล์นี้อธิบายว่า "อะไรอยู่ตรงไหน" และ "ถ้าจะแก้เรื่องนี้ ให้เปิดไฟล์ไหน"

## 1. ภาพรวม

```
isd-2026-loso/
├── README.MD                  วิธีรันระบบ + ภาพรวมโปรเจกต์ + สมาชิก (เริ่มอ่านที่นี่)
├── docker-compose.yml         รันทั้งระบบ (web + backend) ด้วยคำสั่งเดียว
├── Code.py                    อ่านไฟล์เดียวจากบรรทัดคำสั่ง (เรียก model.extract)
│
├── web/                       ① หน้าเว็บ (Next.js 16 + Tailwind 4)
├── backend/                   ② API (FastAPI) + ฐานข้อมูล SQLite
├── model/                     ③ pipeline OCR + ตัวตรวจ + เครื่องมือวัดผล/ฝึก + รายงานผล
├── data/                      ฐานข้อมูล SQLite ที่ใช้ตอนรันนอก Docker (transcripts.db)
│
├── data_transcript/           ข้อมูลทดสอบ: transcript PDF จริง 48 ไฟล์ (input_Bachelor_Degrees, input_Master)
├── ground_truth_transcript/   เฉลย JSON ของข้อมูลทดสอบ 48 ไฟล์
├── ground_truth_new/          เฉลยของภาพถ่ายมือถือ 2 ชุด (peam.json, pooh.json)
│
└── docs/                      เอกสาร (โจทย์ บันทึกงาน สไลด์)
    ├── STRUCTURE.md           (ไฟล์นี้)
    ├── P1_OCR_Prompt.md       โจทย์ เกณฑ์ให้คะแนน และกำหนดส่ง
    ├── process.md             บันทึกการตัดสินใจ ผลทดสอบ และ checkpoint ตามวันที่
    └── presentation/          สไลด์นำเสนอ
        ├── slide.md           แผนสไลด์ทีละหน้า + สคริปต์พูด + flowchart + ข้อมูลกราฟ
        ├── promt_slide.md     prompt สำหรับให้ AI ช่วยทำสไลด์
        └── slide_assets/      ภาพหน้าจอ application และภาพประกอบ
```

## 2. ลำดับการทำงานของระบบ

```
ผู้ใช้ ──► web (Next.js) ──► /api/proxy ──► backend (FastAPI) ──► model.extract (pipeline OCR)
                                                 │                        │
                                                 ▼                        ▼
                                          SQLite (บันทึก/ค้นหา)     JSON + validation
```

## 3. `web/` — หน้าเว็บ

| พาธ | หน้าที่ |
|---|---|
| `web/app/workspace.tsx` | หน้าเว็บทั้งหมด: นำเข้าไฟล์/ถ่ายรูป, ตรวจ-แก้ผล, ค้นหา, รายละเอียดนักศึกษา |
| `web/app/(workspace)/layout.tsx` | ครอบหน้าทั้งหมดไว้ใน layout เดียว เพื่อให้ผลที่อ่านไว้ไม่หายเมื่อสลับหน้า |
| `web/app/(workspace)/upload/`, `search/`, `search/[studentId]/` | เส้นทาง URL: `/upload`, `/search`, `/search/รหัสนักศึกษา` (ไฟล์ `page.tsx` เหล่านี้คืนค่า null เพราะ URL ทำหน้าที่เลือกมุมมองที่ `workspace.tsx` แสดง) |
| `web/app/page.tsx` | `/` redirect ไป `/upload` |
| `web/app/api/proxy/[...path]/route.ts` | ส่งต่อคำขอจากเบราว์เซอร์ไป backend (ตัวแปร `OCR_API_URL`) |
| `web/Dockerfile` | build แบบ production (Next.js standalone) |

## 4. `backend/` — API และฐานข้อมูล

| พาธ | หน้าที่ |
|---|---|
| `backend/app/main.py` | endpoint ทั้งหมด: `/api/transcripts/extract`, `/api/validate`, `/api/documents`, `/api/students`, `/api/grades`, `/api/suggest`, `/api/health` และตรวจไฟล์ที่อัปโหลด |
| `backend/app/database.py` | ตาราง SQLite (`students`, `documents`, `semesters`, `course_results`) และฟังก์ชันบันทึก/ค้นหา |
| `backend/tests/` | เทสต์ของ backend |
| `backend/requirements.txt`, `backend/Dockerfile` | แพ็กเกจและ image (ติดตั้ง Tesseract ไทย/อังกฤษ + Poppler) |

## 5. `model/` — pipeline OCR (ส่วนสำคัญที่สุด)

| กลุ่ม | ไฟล์ | หน้าที่ |
|---|---|---|
| **จุดเข้า** | `extract.py` | pipeline หลัก: อ่าน PDF/ภาพ → OCR → แปลงเป็น JSON (backend และ `Code.py` เรียกไฟล์นี้) |
| **ขั้นตอนของ pipeline** | `photo_geometry.py` | หาขอบกระดาษและแก้เอียงของภาพถ่าย |
| | `layout_ocr.py`, `cell_ocr.py` | หาคอลัมน์ตารางและ OCR แยกช่อง |
| | `phone_table.py`, `screen_table.py`, `photo_unofficial.py` | ตัวอ่านเฉพาะภาพถ่ายมือถือ/หน้าจอ |
| | `course_catalog.py` | ซ่อมข้อความด้วย catalog รหัสวิชาที่สร้างจากชุด dev |
| | `validate.py` | กฎตรวจความถูกต้อง (รหัส 8 หลัก, GPA 0–4 ฯลฯ) |
| **การวัดผล (ไลบรารี)** | `manifest.py`, `evaluate.py` | แบ่งชุด dev/test ระดับเอกสาร และฟังก์ชันคำนวณ accuracy/row F1 |
| **ข้อมูลของโมเดล** | `formats.json` | นิยามรูปแบบเอกสาร 4 แบบ |
| | `data/` | `manifest.json` (การแบ่งชุด), `course_catalog.json`, ไฟล์โมเดล Tesseract ที่ฝึกเพิ่ม (`phone_ocr/`, `photo_ocr/`) |
| **เครื่องมือ** | `tools/` | สคริปต์วัดผล/ฝึก/วัดเวลา (ตารางข้างล่าง) |
| **เทสต์** | `tests/` | unit test ของ pipeline (93 รายการ + 3 subtests) |
| **ผลลัพธ์** | `reports/` | รายงานผลทดสอบดิบ (JSON) ทุกชุด รวมเวลารายขั้น `step-timing-20261009.json` |
| | `runs/` | ผลรายเอกสารของรอบวัดหลัก (final-dev, final-test ฯลฯ) |

> **กติกา:** ไฟล์แกนใน `model/` ไม่ควรย้ายหรือเปลี่ยนชื่อ เพราะ backend และสคริปต์ import ผ่าน `model.extract`, `model.validate` ฯลฯ

### `model/tools/` — เครื่องมือ (รันจากโฟลเดอร์รากด้วย `python -m model.tools.ชื่อ`)

| กลุ่ม | สคริปต์ | ทำอะไร |
|---|---|---|
| วัดผล PDF | `benchmark.py` | รัน extraction บนชุดที่แบ่งไว้โดยไม่อ่านเฉลย |
| | `compare_routes.py` | เทียบ Hybrid (ข้อความฝัง) กับ Tesseract ล้วนบน PDF ชุดเดียวกัน |
| | `challenge_latency.py`, `challenge_api.py` | วัดเวลา/batch (ตรงๆ และผ่าน API จริง) |
| วัดผลภาพ | `benchmark_images.py` | ภาพต้นฉบับ (แยกจากคะแนน PDF) |
| | `benchmark_augmented.py`, `benchmark_noise_all.py` | ภาพ augmented และภาพ noise |
| | `benchmark_catalog_cv.py` | วัดโดยกันเอกสารออกจาก catalog (ป้องกัน overfit) |
| | `benchmark_photo_angles.py`, `benchmark_phone_ocr.py` | ภาพถ่ายหลายมุม / ภาพมือถือ |
| | `benchmark_vlm.mjs` | ทดลอง Local VLM (Node.js + Ollama) |
| ตรวจเฉลย | `audit_ground_truth.py`, `score_with_audit.py` | ตรวจเฉลยเทียบภาพจริงและคิดคะแนนแบบ audit |
| ปรับค่า/ฝึก | `tune_image_ocr.py` | เลือกวิธีปรับภาพและโหมด Tesseract จากชุด dev |
| | `train_course_catalog.py` | สร้าง catalog จากชุด dev เท่านั้น |
| | `train_phone_ocr.py`, `train_photo_ocr.py`, `evaluate_photo_ocr.py` | ฝึก/ประเมิน Tesseract จากภาพถ่าย (ต้องติดตั้ง `photo_training_requirements.txt`) |
| วัดเวลา | `profile_steps.py` | เวลารายขั้นตอนของ pipeline (วิธีรันอยู่ในหัวไฟล์) |

หมายเหตุ: สคริปต์ `benchmark_images/augmented/noise_all/catalog_cv` และ `audit_ground_truth` อ่านภาพจากโฟลเดอร์ `all/Lab5_transcript_dataset/images` ซึ่ง **ไม่อยู่ใน repo** (โฟลเดอร์ `all/` ยังอยู่ใน `.gitignore`) จึงรันซ้ำได้เฉพาะเมื่อมีภาพชุดนี้ ส่วนสคริปต์ที่ใช้ `data_transcript/` และ `ground_truth_transcript/` (เช่น `benchmark.py`, `compare_routes.py`) รันได้จาก repo ตรงๆ

## 6. ค้นหาให้เร็ว (ถ้าจะแก้เรื่อง... ให้เปิด...)

| อยากแก้ | เปิดไฟล์ |
|---|---|
| หน้าตาหน้าเว็บ / ข้อความในหน้าเว็บ | `web/app/workspace.tsx` |
| เพิ่ม/แก้ API | `backend/app/main.py` |
| ตาราง/คำสั่ง SQL | `backend/app/database.py` |
| เกณฑ์เลือกข้อความฝังหรือ OCR, พารามิเตอร์ OCR | `model/extract.py` (`text_is_usable`, `read_document`) |
| กฎตรวจความถูกต้อง | `model/validate.py` |
| การแก้ภาพเอียง | `model/photo_geometry.py` |
| รูปแบบเอกสาร 4 แบบ | `model/formats.json` |
| รหัสวิชา/ชื่อวิชาที่ซ่อมได้ | `model/data/course_catalog.json` (สร้างใหม่ด้วย `train_course_catalog.py`) |
| ผลทดสอบ / ตัวเลขในสไลด์ | `model/reports/`, `docs/process.md` |

## 7. สิ่งที่สร้างขึ้นเอง ไม่ต้องแก้ด้วยมือ
- `web/node_modules/`, `web/.next/` — สร้างตอน build/ติดตั้ง (ไม่อยู่ใน git)
- `**/__pycache__/` — ไฟล์ Python ชั่วคราว (ไม่อยู่ใน git)
- `model/reports/*.json`, `model/runs/` — ผลที่สคริปต์ใน `model/tools/` สร้าง
