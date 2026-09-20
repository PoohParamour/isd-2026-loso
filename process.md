# Process Log - P1 OCR Transcript

อัปเดต: 2026-09-20

## สถานะ

| งาน | สถานะ | หลักฐาน/หมายเหตุ |
|---|---|---|
| ตรวจโจทย์และข้อมูลเดิม | เสร็จ | อ่าน `P1_OCR_Prompt.md`, สไลด์ใน `all/`, Lab 4-10 และสำรวจ PDF/ground truth |
| ชุดข้อมูลและ split | เสร็จ | 48 PDF, label จับคู่ได้ 47; dev 35/test 12/unlabeled 1; แยกตามเอกสารต้นทาง |
| ตัววัดผลแบบ structured | เสร็จ | exact field, CER, row P/R/F1 และ matrix แยกกลุ่ม |
| OCR และ format routing | เสร็จสำหรับ PDF; ภาพดีขึ้นแต่ยังไม่ผ่านทุกกลุ่ม | PDF text + Tesseract fallback; image preprocessing/PSM แยก 4 profiles |
| Backend, DB, Web | เสร็จขั้น integration | FastAPI + SQLite + Next.js/Tailwind; ทดสอบ upload, save, query ผ่าน API แล้ว |
| Docker และการทดสอบส่งท้าย | ผ่าน end-to-end ขั้นหลัก | Compose web+backend healthy; upload, save และ query ผ่านเว็บ proxy |

## Weekly Mapping

| Week | เนื้อหาใน `all/` | ตัวอย่างที่พบ | การใช้กับ P1 |
|---|---|---|---|
| 1 | Intro, Git, rubric | ตัวอย่าง Git ในสไลด์ | ตั้ง branch, โครงงาน, เกณฑ์ส่ง |
| 2 | Computer Vision | ไม่พบโค้ด lab เฉพาะสัปดาห์ | เตรียมภาพและวิเคราะห์ noise; สร้างเอง |
| 3 | ML/DL foundations | ไม่พบโค้ด lab เฉพาะสัปดาห์ | baseline และการแบ่งข้อมูล; สร้างเอง |
| 4 | CNN/RNN | `Lab4/` | ตัวอย่าง extraction และ schema |
| 5 | Generative modeling | `Lab5_transcript_dataset/` | ภาพ original/augmented และ manifest |
| 6 | Reinforcement Learning | `Lab6_ocr_evaluation/` | ทบทวน metric; RL ไม่ใช่โมเดล OCR หลัก |
| 7 | LLM/prompt | `Lab_7_groupA_transcript/` | ทดลอง local VLM และ structured output |
| 8 | เอกสารมี noise, denoise, text-to-SQL | `Lab8a_ocr_system/` | robustness, postprocessing และการตรวจ hallucination |
| 9 | Evaluation/overfitting | ไม่พบโค้ด lab เฉพาะสัปดาห์ | split ตามฉบับ, CER, field accuracy; สร้างเอง |
| 10 | API/FastAPI | `lab10_fastapi/` | API upload, pipeline, error handling |
| 11 | Frontend ตามตารางวิชา | ไม่พบเอกสารแยก | สร้าง Next.js UI เอง |
| 12 | Backend ตามตารางวิชา | ใช้ Chapter 10/Lab 10 เป็นฐาน | DB และ integration |
| 13 | Challenge ตามตารางวิชา | ไม่พบเอกสารแยก | ทดสอบ format และ latency เอง |

## Decision Log

| วันที่ | เรื่อง | การตัดสินใจ | เหตุผล/แหล่งข้อมูล |
|---|---|---|---|
| 2026-09-20 | ข้อมูล | ใช้ PDF ที่ได้รับอนุญาตเป็นชุดหลัก ไม่ถือ synthetic เป็น deliverable บังคับ | ผู้ใช้ยืนยันว่าอาจารย์อนุญาตให้ใช้ real อย่างเดียว; ต่างจาก prompt เบื้องต้น |
| 2026-09-20 | โบนัส | เลือก latency <30 วินาทีพร้อม batch เป็นโบนัสหลัก; รองรับหลาย format เป็นความสามารถเสริม | benchmark baseline ใหม่บน dev 35 ฉบับเฉลี่ย 0.94 วินาทีและสูงสุด 5.78 วินาที; การนับปริญญาตรี/บัณฑิตศึกษาเป็นฟอร์มเก่า/ใหม่ยังไม่แน่ชัด |
| 2026-09-20 | เกณฑ์คุณภาพ | เป้าหมาย exact field accuracy >91% บน test ที่ล็อกไว้ แสดงผลแยก format และชนิดอินพุต | สไลด์ Chapter 1 rubric; Lab 6 ใช้ fuzzy substring จึงไม่ใช่ผล structured extraction |
| 2026-09-20 | PDF text | ใช้ text layer เฉพาะเมื่อผ่านการตรวจคุณภาพข้อความ มิฉะนั้นส่งเข้า OCR | บาง PDF มี text layer แต่ได้อักขระเพี้ยนเมื่อถอดข้อความ |
| 2026-09-20 | โครงระบบ | Next.js + Tailwind, FastAPI, Docker; local Ollama สำหรับ OCR ที่ต้องใช้ VLM | ผู้ใช้ยืนยัน stack; เครื่องมี Ollama และโมเดลที่ Lab ใช้ |
| 2026-09-20 | ข้อมูลผิดคู่ | ไม่จับคู่ PDF `74176008` กับ JSON `74176005`; กันออกจาก scoring จนตรวจ label | รหัสภายใน PDF คือ `74176008`, ใน JSON คือ `74176005` และรายละเอียดไม่ตรงกัน |
| 2026-09-20 | Local VLM | ไม่ใช้ Typhoon-OCR + Qwen3 เป็นเส้นทางหลัก; คง hybrid PDF text + Tesseract fallback | ทดสอบผ่าน Ollama local กับ PNG 150 DPI แบบสมดุล 4 กลุ่ม: สำเร็จ 1/4, อีก 3 timeout; ฉบับที่สำเร็จถูก 1/75 (1.33%) และใช้ 121.1 วินาที จึงด้อยกว่าทั้ง accuracy และ latency |
| 2026-09-20 | Image OCR profiles | เลือก preprocessing และ PSM แยกตาม format จาก dev 12 ฉบับ; ไม่ใช้ parser heuristic ที่ทำให้ผลรวมลด | tuning 144 runs: bachelor_th original/PSM4, bachelor_en sharpen/PSM6, graduate_th sharpen/PSM4, graduate_en autocontrast/PSM4; accuracy original PNG เพิ่ม 54.31% → 64.43% |
| 2026-09-20 | Validation | ตรวจโครงสร้างและช่วงค่าหลัง OCR พร้อมแสดง error/warning บนหน้า review; ไม่ใช้ GPA คำนวณย้อนหรือ ground truth | ลดความเสี่ยงบันทึก student ID, course ID, credit, grade, semester และ GPA ที่รูปแบบผิด โดยไม่เดาค่าที่อ่านไม่ออก |

## นิยามการวัดผล

### ผลล่าสุด PDF

| ชุด | ฉบับ | ฟิลด์ถูก/ทั้งหมด | Exact field accuracy | สถานะ |
|---|---:|---:|---:|---|
| Dev | 35 | 4394/4551 | 96.55% | ผ่านเป้า >91% |
| Test ครั้งแรก (blind) | 12 | 1182/1338 | 88.34% | ไม่ผ่าน |
| Test หลังปรับ OCR | 12 | 1306/1338 | 97.61% | ผ่านเชิงตัวเลข แต่ใช้ชุดเดิมวิเคราะห์แล้ว |

Test หลังปรับไม่ใช่ independent holdout ใหม่ เพราะผู้ใช้ไม่มี transcript จริงเพิ่ม. รายงานฉบับส่งต้องแสดงทั้งสองรอบ. ผลภาพ PNG แยกจาก PDF และยังไม่ผ่านเป้า.

### โบนัสที่เลือก: Latency และ batch

Docker Compose บนเครื่อง M4 16 GB รัน batch PDF จาก dev 12 ฉบับผ่าน Next.js proxy ไปยัง FastAPI และเปรียบเทียบ ground truth ทุกฉบับ: รวม 21.056 วินาที, เฉลี่ย 1.754 วินาที/ฉบับ, มัธยฐาน 0.078 วินาที, สูงสุด 14.972 วินาที, exact field 96.49%. ผ่านเกณฑ์เฉลี่ย <30 วินาที และมี batch จริง. ผลอยู่ใน model/reports/challenge-api-dev.json.

### ขอบเขตภาพสแกน

PNG original 150 DPI ที่สุ่มแบบสมดุลจาก dev 12 ฉบับ หลังเลือก image profile จาก dev: 808/1254 = 64.43%, row F1 82.74%, เฉลี่ย 5.83 วินาที/ฉบับ. ไทย ป.ตรี 52.71%; อังกฤษ ป.ตรี 94.97%; ไทยบัณฑิต 27.24%; อังกฤษบัณฑิต 77.07%. ดีขึ้นจาก baseline 54.31% แต่ยังต่ำกว่าเกณฑ์รวม. ห้ามอ้างผล PDF เป็นผลภาพสแกน.

ภาพ augmented 5 แบบจาก dev 12 ฉบับ รวม 60 ภาพ: 2234/6270 = 35.63%, row F1 51.75%, เฉลี่ย 7.35 วินาที/ฉบับ, สูงสุด 25.62 วินาที. Latency ยังผ่าน <30 วินาที แต่ robustness ไม่ผ่าน โดย blur/contrast, perspective และ JPEG/dark เป็นจุดอ่อนหลัก. รายงานอยู่ใน `model/reports/image-augmented-dev.json`.

### Cost-benefit ของเส้นทางที่ทดสอบบน PDF 8 ฉบับเดียวกัน

| เส้นทาง | Exact field | เวลาเฉลี่ย | ค่า API |
|---|---:|---:|---:|
| Hybrid PDF text + Tesseract fallback | 565/575 = 98.26% | 0.433 วินาที | 0 USD |
| Tesseract OCR ทุก PDF | 241/575 = 41.91% | 3.227 วินาที | 0 USD |

สองแถวนี้เป็นการเปรียบเทียบเส้นทาง OCR ไม่ใช่สองโมเดลที่ต่างกัน. ใช้ hybrid เพราะแม่นกว่าและเร็วกว่าในไฟล์ที่มี text layer; ผล local VLM แยกไว้ด้านล่างเพราะรับภาพ PNG ไม่ใช่ digital PDF.

### Local VLM ตาม Lab 7

ทดสอบ `scb10x/typhoon-ocr1.5-3b -> qwen3:4b` ผ่าน Ollama local กับภาพ original 150 DPI จาก dev แบบสมดุล 4 กลุ่ม กลุ่มละ 1 ฉบับ. ปริญญาตรีไทยประมวลผลสำเร็จแต่ได้เพียง 1/75 = 1.33% และใช้ 121.1 วินาที; ปริญญาตรีอังกฤษ บัณฑิตไทย และบัณฑิตอังกฤษ timeout ที่ 120 วินาทีในขั้น OCR. ผลนี้ไม่ผ่านเป้า <30 วินาทีและไม่เหมาะเป็นเส้นทางหลัก. รายงานอยู่ที่ `model/reports/vlm-dev.json`; Markdown/JSON กลางทางอยู่ใน `model/reports/vlm-intermediate/`. ตัวเลขนี้เป็น image-input benchmark จึงไม่ปะปนกับคะแนน digital PDF.

- Primary: exact match ของฟิลด์ที่มีค่าใน ground truth หลัง normalization ที่ประกาศไว้ล่วงหน้า; ฟิลด์หายถือว่าผิด
- แถวรายวิชาที่หาย/เกินต้องรายงานแยก และไม่ทำให้คะแนนดูดีจากฟิลด์ว่างจำนวนมาก
- Secondary: CER, row precision/recall/F1, critical-field accuracy, latency และค่าใช้จ่าย
- แยกผล PDF ดิจิทัลกับภาพสแกน/ภาพถ่าย; แยกปริญญาตรี/บัณฑิตศึกษาและไทย/อังกฤษ
- ไม่ใช้ ground truth ของ test ใน inference, parser config, postprocessing หรือทะเบียนรหัสวิชา

## Blockers / ความเสี่ยง

- เกณฑ์โบนัสยกตัวอย่างฟอร์มเก่า/ใหม่; ต้องแสดงให้เห็นความต่างของ layout อย่างน้อย 2 แบบ ไม่อ้างเพียงระดับปริญญา
- ผล Lab 8 เดิมเป็นตัวอย่างเดียว: accuracy 62.4%, เวลา 93 วินาที; ยังไม่ใช่ผลรวมของระบบใหม่
- PNG จาก Lab 5 เป็นภาพ 150 DPI และ OCR ไทยยังต่ำกว่าเป้า; ห้ามรวมผลภาพกับ PDF หรืออ้างว่า robustness ผ่านแล้ว
- `README.MD` และ `.gitignore` เดิมมีข้อห้ามแก้ตาม prompt; เพิ่มไฟล์คู่มือ/ignore เฉพาะส่วนใหม่เมื่อจำเป็น

## Next Steps

- [x] สร้าง manifest และ split คงที่ตาม PDF ต้นทาง
- [x] สร้าง evaluator ของผล JSON จริงและ benchmark baseline
- [x] ทำ format configs + pipeline PDF/OCR
- [x] ทำ FastAPI, DB และ Next.js
- [x] ยืนยัน Docker end-to-end และวัด batch ผ่าน deployed API
- [x] ทดลอง local VLM ตาม Lab 7 บนชุดสมดุล; บันทึก accuracy, latency และ timeout เพื่อใช้ตัดสินใจเลือกโมเดล
- [x] ขยาย image benchmark ไปยัง original/augmented และเลือก preprocessing/PSM แยกตาม 4 format
- [x] เพิ่ม structural validation และแสดง error/warning บนหน้า review ก่อนบันทึก
- [ ] เพิ่ม deskew/perspective correction และ table row/cell segmentation โดยเน้นบัณฑิตไทย
- [ ] ทำ candidate selection จาก structural confidence แล้ววัดซ้ำบน dev โดยห้ามเลือกจากชื่อ augmentation
- [ ] จัดทำ docs และสไลด์ช่วงท้าย

## แผนปิดโปรเจกต์และเกณฑ์ผ่านแต่ละช่วง

| ช่วงตามเอกสาร | งานที่ต้องเสร็จ | หลักฐานที่ต้องแสดง |
|---|---|---|
| Checkpoint 1 และ Proposal (เริ่มใหม่ย้อนหลัง) | ระบุโจทย์, สิทธิ์ใช้ PDF จริง, schema JSON, data audit, split และนิยาม metric | manifest 48 ฉบับ, 47 label ที่จับคู่ได้, orphan/unlabeled ระบุชัด, process log |
| Checkpoint 2 และ Mid-project Review | เทียบ hybrid กับ OCR ล้วนและ local VLM ด้วยข้อมูลเดียวกันเท่าที่รันได้; วิเคราะห์ error | matrix field accuracy/CER/row F1/latency/cost, เหตุผลเลือกโมเดล, Code.py หรือ entrypoint |
| Checkpoint 3: 28 ก.ย. | upload → extract → review → save → grade query ผ่าน UI และ API | Docker Compose healthy, ทดสอบไฟล์จริงทั้งไทย/อังกฤษและ ป.ตรี/บัณฑิต |
| Challenge: 5 ต.ค. | ส่งผลโบนัส latency จาก batch ผ่าน deployed API และผลภาพ original/augmented แยกประเภท | average <30 วินาทีรวม comparison; batch อย่างน้อย 12 ฉบับ; matrix ความแม่นยำแต่ละสภาพภาพ |
| Code Freeze: 12 ต.ค. | แก้ defect ที่พบ, ล็อก dependencies และผล benchmark, ทดสอบเริ่มระบบใหม่ | commit/release tag, smoke test, ไม่มีแก้ฟีเจอร์หลัง freeze |
| Final: 19 ต.ค. | เอกสารใช้งาน, architecture, report ไม่เกิน 10 หน้า, slide/demo 10 นาที + Q&A 3 นาที | README/คู่มือ/สไลด์ และ checklist ส่งงานครบ |

เกณฑ์คุณภาพหลัก: exact match ของฟิลด์ที่มีค่าใน ground truth >91% พร้อม matrix แยกหมวดและรูปแบบ; row F1, CER และ latency รายงานควบคู่. ผล PDF หลังแก้ผ่านเชิงตัวเลข แต่ต้องรายงาน blind 88.34% และข้อจำกัดชุดทดสอบเดิมด้วย. ภาพต้นฉบับยังไม่ผ่าน ต้องเพิ่ม OCR ภาพภาษาไทยหรือระบุข้อจำกัดในงานส่ง ไม่ใช้คะแนน PDF กลบข้อบกพร่อง.

งานภายนอก repo ที่ทีมต้องทำ: เชิญอาจารย์เข้าถึง GitHub ตามอีเมลในโจทย์, ส่ง checkpoint/เอกสารในช่องทางวิชา และซ้อม demo. ยังไม่ได้ดำเนินการแทนผู้ใช้.

## Changelog

- 2026-09-20 - เริ่ม process log และล็อกเป้าหมายโบนัส/metric บน `feature/ocr-core`
- 2026-09-20 - สร้าง manifest (dev 35/test 12/unlabeled 1), evaluator และ baseline; dev ได้ exact field accuracy 94.1% ก่อนการแก้ transfer/header เพิ่มเติม
- 2026-09-20 - blind test PDF 12 ฉบับได้ 1182/1338 = 88.34%; ปรับ OCR อังกฤษ ป.ตรี แล้วรันชุดเดิมได้ 1306/1338 = 97.61% (ชุดเดิมจึงไม่เป็น blind)
- 2026-09-20 - final dev PDF 35 ฉบับได้ 4394/4551 = 96.55%; course 97.52%, header 99.46%, semester 96.68%, summary 90.00%, footer 69.29%; row F1 98.53%
- 2026-09-20 - เพิ่ม API/SQLite, หน้าเว็บ Next.js และ Docker Compose; local API upload-save-search ผ่าน
- 2026-09-20 - Docker web+backend healthy; proxy upload-save-search ผ่าน; deployed batch 12 ฉบับเฉลี่ย 1.754 วินาทีรวม comparison
- 2026-09-20 - ภาพ PNG original dev 12 ฉบับได้ 54.31%; เป็นข้อจำกัดสำคัญที่ต้องแยกจากคะแนน PDF
- 2026-09-20 - อ่าน `all/` ชุดอัปโหลดใหม่และยืนยัน Lab 7 pipeline; ทดสอบ local VLM 4 กลุ่มผ่าน Ollama ได้ 1/75 ในฉบับที่สำเร็จ (121.1 วินาที) และอีก 3 ฉบับ timeout ที่ 120 วินาที
- 2026-09-20 - tune preprocessing × PSM 144 runs; เพิ่ม image profiles ทำให้ original PNG dev 12 ฉบับดีขึ้น 54.31% → 64.43%, row F1 82.74%, เฉลี่ย 5.83 วินาที
- 2026-09-20 - augmented benchmark 60 ภาพได้ 35.63%, row F1 51.75%, สูงสุด 25.62 วินาที; เพิ่ม validation ใน API/UI; PDF regression ยังผ่าน 96.62%
