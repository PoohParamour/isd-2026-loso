# Process Log - P1 OCR Transcript

อัปเดต: 2026-10-07

> หมายเหตุ (2026-10-09): ไฟล์ถูกย้ายมาไว้ที่ `docs/` และสคริปต์ใน `model/` แยกเป็น `model/tools/` (วัดผล/ฝึก) กับ `model/tests/` (เทสต์) บันทึกด้านล่างที่อ้างตำแหน่งเดิม เช่น `model/benchmark.py`, `model/test_*.py`, `process.md` ให้อ่านเป็นตำแหน่งใหม่ตามนี้ ผังโครงสร้างปัจจุบันอยู่ที่ [STRUCTURE.md](STRUCTURE.md)

## Reports review — 2026-10-07

- ตามคำขอผู้ใช้ อ่านรายงานทั้งหมดใน `model/reports` และ aggregate reports ใน `model/runs`: รวม 89 ไฟล์ (JSON 81, CSV 6, Markdown 2). JSON อ่านได้ครบ; ตรวจ accuracy เทียบ correct/total 1,854 จุด, CSV 6 ไฟล์เทียบ report คู่กัน และ totals ที่มี details ไม่พบ mismatch ในรายการที่ตรวจ. ไม่รัน OCR/training/benchmark ใหม่และไม่แก้รายงานเดิม
- สรุปแยกชนิดอินพุต/รุ่น/ชุดทดสอบ ไม่รวมรายงานที่ทับซ้อนกันเป็น accuracy เดียว: PDF dev ล่าสุด 4397/4551 = 96.62%, reused PDF test 1307/1338 = 97.68% (blind ครั้งแรก 1182/1338 = 88.34%); original PNG ล่าสุด 1281/1338 = 95.74%, row F1 100%; grain-noise 47 ภาพ 5445/5889 = 92.46%, แต่ graduate_th 935/1046 = 89.39%; augmented mixed dev 60 ภาพ 4373/6270 = 69.74%; ภาพถ่ายจอเดิม 4 มุม 423/600 = 70.50%; ภาพกล้องใหม่ 6 ภาพ 861/885 = 97.29%, row F1 99.46%
- ภาพกล้องใหม่ผิด 24 ฟิลด์: subject_name 13, issue date 4, grade 3 (null), person name 2, prename 1, course ID 1. Header 33/36, footer 2/6, summary 12/12, semester 126/126, course 688/705. GPA รายภาค 33/33, GPS 27/27 และ GPA สะสม 6/6; student IDs 6/6. ชื่อวิชาและวันที่ยังเป็นข้อจำกัด แม้คะแนนรวมสูง
- `phone-all-final-20261007.json` และ `phone-training-summary-20261007.json` เป็นผล phone ล่าสุดที่ใช้สรุป; `phone-final-development` เป็น snapshot ก่อนแก้ GPA รอบท้าย (572/590) ส่วน development_final ใน summary เป็น subset จาก all-final (574/590) จึงต่างกันอย่างอธิบายได้. `phone-final-angle-test` คือผลแรก 85.42%; หลังนำมุม 3 วิเคราะห์แล้วต้องเรียก reused test 97.29%. ชื่อ final/test ในไฟล์เก่าไม่ได้รับรองว่าเป็นผล blind หรือโมเดลรุ่นปัจจุบัน
- หลักฐาน latency: deployed PDF batch 12 ฉบับเฉลี่ย 1.754 วินาที, phone final 27.539 วินาที; augmented dev เฉลี่ย 14.22 แต่สูงสุด 44.33 วินาที. ไม่อ้างว่าโทรศัพท์ใหม่พิสูจน์ robustness ของ blur/perspective/dark ทั้งชุด หรือ deployment Docker ปัจจุบัน. Local VLM รายงานเดิมสำเร็จ 1/4, 1/75 ฟิลด์, อีก 3 timeout; ใช้เป็นเหตุผลเลือกเส้นทางหลักบนเครื่องที่ทดสอบเท่านั้น
- Label audits พบ test mismatch 23 ฟิลด์ (วันที่ 10, phantom final-semester fields 12, เครดิต 1); ต้องคง raw-label/audited scores แยกกัน. ผล document-held-out catalog 92.11% ลดการปนเปื้อนจาก catalog แต่ parser ยังเคยปรับบน dev จึงไม่ใช่ independent document holdout ใหม่
- ข้อสรุป: PDF/ภาพต้นฉบับ/ภาพกล้องใหม่ในชุดที่ตรวจผ่าน >91%; mixed robustness ยังไม่ผ่าน และยังต้องวัดเอกสารใหม่ที่ไม่เคยใช้ปรับระบบ. รายงานแต่ละกลุ่มมาจากคนละช่วงโค้ด/runtime; ไม่รวมเป็นคะแนนความแม่นยำทั่วไปเดียว. Inventory/checks อ่านอย่างเดียวอยู่ใน ignored `tmp/report_review/`; รอบนี้แก้เฉพาะ process log

## Phone OCR training — 2026-10-07 (เสร็จรอบนี้)

- ผู้ใช้อนุญาตให้ฝึกและทดสอบวนซ้ำจาก `data_transcript/input_photo`: HEIC 3024×4032 px 6 ภาพ, peam/pooh อย่างละ 3 มุม พร้อม ground truth ใน `ground_truth_new`. คงไฟล์ต้นฉบับและ label ไว้
- แบ่งมุม 1 เป็น train, มุม 2 เป็น validation สำหรับเลือก checkpoint/preprocessing และมุม 3 เป็น final angle holdout; ห้ามนำมุม 3 ไปฝึกหรือปรับจาก error จนจบการเลือก. ทั้งสองเอกสารเคยใช้ฝึกโมเดลภาพเดิมแล้ว จึงไม่ใช่ independent document holdout
- เป้าหมายเบื้องต้น exact field >91%, row F1 และ critical fields (student/course IDs, grades, GPA) ต้องรายงานแยก; ไม่รับรองความแม่นยำทั่วไปจากเอกสารเพียงสองฉบับ. เลือกเริ่ม fine-tune Tesseract LSTM จาก float English model ด้วย line crops ที่ตรวจ alignment กับ PDF/GT; เปรียบเทียบ installed/เดิม/best และ checkpoint หลายระดับก่อนนำใช้จริง. ใช้ PDF จัดแนวและ label เฉพาะขั้น training preparation ไม่ใช้ inference
- สร้าง `.venv-photo` ใน workspace จาก Python 3.12 ที่มีอยู่และเพิ่ม dependencies สำหรับ HEIC/PDF/pytest; runtime ต้องผ่าน sandbox escalation เพราะ Python base อยู่นอก writable root. Docker daemon ยังไม่พร้อม. หลักฐาน Tesseract training: https://tesseract-ocr.github.io/tessdoc/tess5/TrainingTesseract-5.html
- เลือก fine-tune จาก float English tessdata_best ใหม่ ไม่ต่อจาก weights ภาพเดิม. จัดแนว PDF เฉพาะการเตรียม supervised crops ด้วย SIFT/RANSAC; 109 train lines จากมุม 1 และ 109 validation lines จากมุม 2. Exclude issue dates/signatures ที่อาจต่างระหว่าง export; ไม่เพิ่มคำตอบจาก GT เป็น dictionary หรือ hardcode รหัส/ชื่อ/GPA ใน inference
- ทดลอง 4 รอบ: 100 iterations lr 0.0001 ได้ validation CER 6.17%; 300 ได้ 2.31%; 600 ได้ 2.49%; 300 lr 0.0003 ได้ 2.31% เท่ากัน. Installed/best baseline CER 8.83%, weights ภาพเก่า 7.86%. เลือก 300 iterations lr 0.0001; exact validation lines 79/109. แก้ training configuration ของ Windows ให้ใช้ OEM 1, config path ชัดเจน และ list files เป็น LF; ตรวจว่า LSTMF ถูกสร้างจริงก่อนฝึก
- เพิ่ม `model/phone_table.py`: หาเส้นตารางด้วยการชดเชย shear ±0.03, แยกบรรทัดจาก ink projection, อ่านหัวเอกสารซ้าย/ขวาและช่องเครดิต/เกรดแยกกัน. เพิ่ม `straighten_clipped_photo` ใช้สามขอบกระดาษที่เห็นกับเส้นตารางล่างเป็น reference เมื่อขอบล่างหลุดเฟรม ไม่อ้างว่าเส้นตารางเป็นขอบกระดาษจริง. เลือกผล GPA จาก recognizer ที่ฝึกเมื่ออ่าน label/ตัวเลขครบและอยู่ในช่วง 0–4; ใช้ generic OCR เป็น fallback เมื่อค่าเดิมอ่านไม่ครบ/เป็นไปไม่ได้ ไม่ให้ generic 2.47 ทับ trained 2.17 ที่อ่านถูก
- Development angles 1/2 ก่อนแก้ 413/590 = 70.00%; เวอร์ชันสุดท้าย 574/590 = 97.29%. การเทียบ layout เดียวกันก่อนแก้ geometry ขั้นท้ายบน validation angles 2: untrained 250/295 = 84.75%, trained 288/295 = 97.63%. ผลนี้แยกประโยชน์จากการฝึกกับการปรับ segmentation; ไม่ใช่ independent document test
- Sealed angle 3 ครั้งแรกได้ 252/295 = 85.42%: Pooh ไม่ผ่าน page boundary จึง fallback ตัวอ่านเดิม และ Peam มีขอบมืดรวมบรรทัดหัวเอกสาร. เก็บผลครั้งแรกไว้ที่ `phone-final-angle-test-20261007.json`; หลังตรวจ error และแก้ geometry ชุดนี้ต้องเรียก reused test: 287/295 = 97.29%, row F1 98.39%. ไม่เพิ่มมุม 3 เข้า recognizer training และไม่อ้างเป็น blind result หลังแก้
- Final production pipeline ครบ 6 HEIC ได้ **861/885 = 97.29%**; แยก Peam มุม 1/2/3 = 149/150,145/150,146/150 และ Pooh = 138/145,142/145,141/145 (ทุกภาพ >91%). Course row F1 99.46% (185 TP/1 FN/1 FP), student IDs 6/6, course IDs 185/186, เกรดที่มีค่า 144/147, GPA รายภาค 33/33, GPS 27/27 และ GPA สะสม 6/6. เฉลี่ย 27.539 วินาที/ภาพ, สูงสุด 28.641 วินาทีในรอบ final บนเครื่องนี้; ไม่รับประกัน latency ทุกเครื่อง/ภาพ. ยังผิดชื่อบางส่วน วันที่ออกเอกสาร และรหัสวิชา 9 หลักหนึ่งช่องซึ่ง validation แจ้งตรวจ; คง warning ให้ตรวจภาพถ่ายก่อน save
- Paired regression ภาพ original 12 ฉบับใน runtime เดียวกัน โดยปิด/เปิดเส้นทางใหม่: **1281/1338 = 95.74%**, row F1 100%, ทุกฉบับได้คะแนนเท่ากัน. ตัวเลขต่างจากรายงานเก่า 1284/1338 จึงไม่ใช้รายงานคนละ runtime เป็นฐานอ้าง regression. Unit tests 93 รายการ + 3 subtests ผ่าน; Ruff โค้ดใหม่และ git diff --check ผ่าน
- เก็บ weights ใหม่แยกที่ `model/data/phone_ocr/eng_phone.traineddata` พร้อม `training.json` และ SHA256; คง weights ภาพเดิม. Backend ใช้ `tesseract_phone` สำหรับภาพ rectified ความละเอียดสูงที่ตรวจพบ unofficial English table และคง fallback เดิม. API smoke ด้วย in-process HTTP client รับ HEIC ได้ HTTP 200/ผล record ตรงกับ CLI/27.172 วินาที; ใช้ SQLite ชั่วคราว ไม่แตะฐานข้อมูลผู้ใช้. ยังไม่เปิด/restart Docker หรือ deploy; runtime ฝึก Python 3.12.3/OpenCV 4.14.0 ต่างจาก Docker requirement ที่ pin 4.12 จึงต้องตรวจใน container ก่อนอ้างผล deployment
- รายงานสรุป `model/reports/phone-training-summary-20261007.json`; raw final `phone-all-final-20261007.json`, validation `phone-validation-{untrained,trained}-20261007.json`, paired originals `phone-original-{paired-baseline,regression}-20261007.json`, API `phone-api-smoke-20261007.json`. Training/crops/checkpoints/debug อยู่ใน ignored `tmp/phone_training/`. Hash ภาพทั้ง 6 คงเดิม ไม่แก้ ground truth/data/all/README/.gitignore เดิม และไม่มี commit

## Context review — 2026-10-07

- ตามคำขอผู้ใช้ อ่าน `P1_OCR_Prompt.md` และทบทวน `process.md`, README, โครงสร้างไฟล์, source หลักใน `model/`, `backend/`, `web/`, entry point `Code.py`, Docker และเส้นทาง Lab 10 ก่อนเริ่มงานต่อ
- ทบทวนเนื้อหาบท 1–10 ผ่านข้อความสไลด์ที่มีอยู่ใน `tmp/context-read/` และภาพสไลด์บท GAN/RL; สำรวจ Lab 4–10 และ dataset/manifest. ไม่ตรวจประกาศ LMS และไม่เปิดภาพ/PDF dataset, รายงานผลกลางทาง, dependencies หรือไฟล์ binary ทุกชิ้นทีละไฟล์
- เข้าใจเส้นทางหลัก: Next.js proxy → FastAPI → PDF text ที่ผ่าน quality gate หรือ Tesseract OCR พร้อม geometry/orientation/layout/cell recovery → structured record/validation → ผู้ใช้ตรวจแก้ → SQLite. เส้นทาง Typhoon OCR + Qwen ของ Lab 10 แยกจาก backend หลัก
- ข้อกำหนดภายหลังใน Decision Log ใช้ประกอบ prompt เบื้องต้น: อาจารย์อนุญาต real dataset อย่างเดียว; manifest มี dev 35/test 12/unlabeled 1; แยกผล PDF/raster, blind/reused test และ document-held-out catalog. ไม่ใช้ test labels หรือชื่อไฟล์เป็นคำตอบระหว่าง inference
- อ่าน `ground_truth_new/peam.json`: 5 ภาค/32 วิชา/GPA สะสม 3.59/หน่วยกิตสะสม 78. ผลภาพถ่ายจอ 4 มุมที่บันทึกไว้เป็น development regression ของเอกสารเดียว: 423/600 = 70.50%, row F1 76.03%, เฉลี่ย 30.90 วินาที; summary/footer ยังอ่านไม่ถูก. Original reused test หลังแก้ภาพจอ 1284/1338 = 95.96%; augmented dev หลัง deskew 4373/6270 = 69.74%. ตัวเลขทั้งหมดเป็นรายงานเดิม ไม่ใช่การรันใหม่วันนี้
- รอบนี้ทำความเข้าใจบริบทและบันทึกเท่านั้น ไม่แก้โค้ด/ข้อมูล/ground truth/prompt, ไม่ train, ไม่รัน tests หรือ benchmark ใหม่, ไม่เปิด/restart server, ไม่ deploy และไม่ commit. คง branch `fix_non` เดิม

## Server startup — 2026-10-04

- ผู้ใช้ขอเปิดเซิร์ฟเวอร์: เปิด Docker Compose แบบ dev. Backend healthy; เว็บเดิมหยุดด้วย `next: not found` จึง build เฉพาะ web และ renew anonymous volumes ของ node_modules/.next แล้วเปิดใหม่ โดยคง data bind mount เดิม
- ตรวจ `http://localhost:3000/upload` ได้ HTTP 200 และ `/api/proxy/health` ได้ status ok, Tesseract/Poppler พร้อมและมี 4 formats. เว็บพอร์ต 3000, API พอร์ต 8000; รอบนี้ยังไม่ได้อัปโหลดภาพหรือทดสอบความแม่นยำใหม่

## Context review — 2026-10-04

- ตามคำขอผู้ใช้ อ่าน `P1_OCR_Prompt.md` และทบทวนสถานะ/Decision Log/Checkpoint ในไฟล์นี้ก่อนเริ่มงานต่อ; สำรวจโครงสร้างข้อมูล โค้ดหลักใน `model/`, `backend/`, `web/`, entry point `Code.py`, Docker และบทบาทของ Lab 4–10
- ตรวจสไลด์ PDF บท 1–10 ใน `all/` โดยถอดข้อความและสำรวจหัวข้อรายหน้า; ตรวจภาพสไลด์ GAN/RL ที่ถอดข้อความได้ไม่ครบเพิ่มเติม. ยืนยัน rubric P1 15/35/40/10 และโบนัสรวมสูงสุด +10 จาก Chapter 1; Chapter 8 จริงเป็น noise/denoise และ structured data/text-to-SQL ไม่ใช่หัวข้อ fine-tune ตามแผนเบื้องต้น. ไม่ได้ตรวจประกาศ LMS
- อ่าน pipeline extraction, geometry/orientation/deskew, layout/cell OCR, catalog, validation, evaluator และไฟล์ benchmark/audit ที่เปิดใน IDE พร้อมหลักฐานรายงานล่าสุด. Original reused test 1281/1338 = 95.74%, row F1 100%; augmented dev 4373/6270 = 69.74%, เฉลี่ย 14.22 วินาที สูงสุด 44.33 วินาที. เป็นผลจากรายงานเดิม ไม่ได้รันใหม่ใน session นี้
- ใช้ข้อยืนยันภายหลังใน Decision Log ประกอบ prompt: อาจารย์อนุญาต real dataset อย่างเดียว, แยก PDF text กับ raster OCR, แยก blind/reused test และ catalog held-out, คง source labels และไม่ใช้ test labels ใน inference
- รอบนี้เป็นการทำความเข้าใจ: ไม่แก้โค้ด/ข้อมูล/ground truth, ไม่ train, ไม่ benchmark, ไม่ deploy และไม่ commit. มีไฟล์ถอดข้อความ/ภาพย่อสำหรับอ่านใน `tmp/context-read/`; ไม่ได้ตรวจภาพ dataset และไฟล์ผลกลางทางทุกชิ้นทีละใบ

## สถานะ

### Metrics review — 2026-10-04

- ผู้ใช้ต้องการตัวเลขความแม่นยำ/คุณภาพใน matrix: รวบรวมรายงานที่มีอยู่ แยก original PNG reused test, augmented PNG dev ตาม format × noise และ PDF dev ตามหมวดฟิลด์. ไม่รัน benchmark ใหม่และไม่แก้โมเดล
- `model/runs/pdf-regression-eval/report.json` ระบุ PDF dev 35 ฉบับ 4397/4551 = 96.62%, row precision 100%, recall 97.24%, F1 98.60%; เป็นผล hybrid (26 PDF text/9 Tesseract ตาม benchmark) จึงไม่ใช้แทนคุณภาพ raster OCR
- Original reused test 12 ฉบับ 95.74%/row F1 100%; augmented dev 60 ภาพ 69.74%/row F1 82.55%, noise 94.58% แต่ blur/contrast 57.18%, perspective 60.37%. ข้อสรุป: ภาพต้นฉบับผ่านเชิงตัวเลข แต่ robustness รวมยังไม่ถึง >91% และยังไม่มี independent document holdout ใหม่

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
| 2026-09-25 | แก้ OCR ภาพถ่าย unofficial อังกฤษหลังฝึกโมเดล | เพิ่ม OCR ตารางแยกจากหัว/ท้ายกระดาษสำหรับภาพที่ปรับมุมแล้วและมีความละเอียดพอ, ยอมรับหัวภาค `151 Semester`, ใช้หัวเอกสารอังกฤษกันการ route เป็นไทย, ไม่เติมชื่อมหาวิทยาลัยเมื่อไม่เห็นในเอกสาร, แจ้งเตือนภาพหน้ากระดาษเล็กกว่า 900 px | `1.jpg` ก่อน 11/145 ฟิลด์และ 10/30 แถว; หลัง 63/145 และ 26/30 แต่ยังมี validation errors 16 ข้อ. `2.png` หน้าเอกสารหลังปรับมุม 595×696 px, หลังแก้ยังได้ 7/150 และ 0/32 แถว จึงต้องใช้ `doc.pdf` ที่มีอยู่หรือถ่ายภาพใหม่คมชัดกว่า; PDF ต้นฉบับได้ 150/150 และ 32/32. รูปแบบเดิม 4 ภาพยังได้ 325/338, 44/44 แถว. รายงาน `model/reports/photo-ocr-fix-20260925.json` |
| 2026-09-25 | ฝึก English OCR จากภาพถ่าย `1.jpg`, `2.png` | จับคู่ `1.jpg` กับ `pooh.pdf`/`ground_truth_new/pooh.json` และ `2.png` กับ `doc.pdf`/`ground_truth_new/doc.json`; ฝึก Tesseract LSTM แยกเป็น candidate ยังไม่แทนตัวอ่านใน production | สองภาพเป็นคนละนักศึกษา. SIFT alignment ได้ 146/297 inliers; ฝึก 49 บรรทัด กัน 13 บรรทัดในสองฉบับไว้ตรวจ. CER ของโมเดล trainable English ลด 27.49% → 11.53% บนบรรทัดที่กันไว้ แต่ full-page PSM6 ยังจับแถวได้ 15/30 ใน pooh และ 0/32 ใน doc จึงต้องแก้ layout/segmentation และทดสอบกับเอกสารใหม่ก่อนนำไปใช้จริง; รายงาน `model/reports/photo-ocr-training.json`, `model/reports/photo-ocr-fullpage.json` |
| 2026-09-25 | ภาพถ่ายหน้าจอ `input_new/1.jpg`, `2.png` | เพิ่ม geometry correction และ partial-row recovery แบบไม่เดาค่าที่อ่านไม่ได้; ยังไม่ fine-tune recognizer จาก 2 ภาพ | baseline 0 วิชาทั้งคู่; ภาพ 1 ไม่มี label อิสระ, ภาพ 2 มี `doc.pdf` ให้เทียบแต่ภาพต่ำกว่า 1 MP. ชุดเล็กนี้ไม่พอประเมินโมเดลที่ฝึกใหม่อย่างน่าเชื่อถือ; ต้องเก็บ label และ holdout เพิ่ม |
| 2026-09-20 | ข้อมูล | ใช้ PDF ที่ได้รับอนุญาตเป็นชุดหลัก ไม่ถือ synthetic เป็น deliverable บังคับ | ผู้ใช้ยืนยันว่าอาจารย์อนุญาตให้ใช้ real อย่างเดียว; ต่างจาก prompt เบื้องต้น |
| 2026-09-20 | โบนัส | เลือก latency <30 วินาทีพร้อม batch เป็นโบนัสหลัก; รองรับหลาย format เป็นความสามารถเสริม | benchmark baseline ใหม่บน dev 35 ฉบับเฉลี่ย 0.94 วินาทีและสูงสุด 5.78 วินาที; การนับปริญญาตรี/บัณฑิตศึกษาเป็นฟอร์มเก่า/ใหม่ยังไม่แน่ชัด |
| 2026-09-20 | เกณฑ์คุณภาพ | เป้าหมาย exact field accuracy >91% บน test ที่ล็อกไว้ แสดงผลแยก format และชนิดอินพุต | สไลด์ Chapter 1 rubric; Lab 6 ใช้ fuzzy substring จึงไม่ใช่ผล structured extraction |
| 2026-09-20 | PDF text | ใช้ text layer เฉพาะเมื่อผ่านการตรวจคุณภาพข้อความ มิฉะนั้นส่งเข้า OCR | บาง PDF มี text layer แต่ได้อักขระเพี้ยนเมื่อถอดข้อความ |
| 2026-09-20 | โครงระบบ | Next.js + Tailwind, FastAPI, Docker; local Ollama สำหรับ OCR ที่ต้องใช้ VLM | ผู้ใช้ยืนยัน stack; เครื่องมี Ollama และโมเดลที่ Lab ใช้ |
| 2026-09-20 | ข้อมูลผิดคู่ | ไม่จับคู่ PDF `74176008` กับ JSON `74176005`; กันออกจาก scoring จนตรวจ label | รหัสภายใน PDF คือ `74176008`, ใน JSON คือ `74176005` และรายละเอียดไม่ตรงกัน |
| 2026-09-20 | Local VLM | ไม่ใช้ Typhoon-OCR + Qwen3 เป็นเส้นทางหลัก; คง hybrid PDF text + Tesseract fallback | ทดสอบผ่าน Ollama local กับ PNG 150 DPI แบบสมดุล 4 กลุ่ม: สำเร็จ 1/4, อีก 3 timeout; ฉบับที่สำเร็จถูก 1/75 (1.33%) และใช้ 121.1 วินาที จึงด้อยกว่าทั้ง accuracy และ latency |
| 2026-09-20 | Image OCR profiles | เลือก preprocessing และ PSM แยกตาม format จาก dev 12 ฉบับ; ไม่ใช้ parser heuristic ที่ทำให้ผลรวมลด | tuning 144 runs: bachelor_th original/PSM4, bachelor_en sharpen/PSM6, graduate_th sharpen/PSM4, graduate_en autocontrast/PSM4; accuracy original PNG เพิ่ม 54.31% → 64.43% |
| 2026-09-20 | Validation | ตรวจโครงสร้างและช่วงค่าหลัง OCR พร้อมแสดง error/warning บนหน้า review; ไม่ใช้ GPA คำนวณย้อนหรือ ground truth | ลดความเสี่ยงบันทึก student ID, course ID, credit, grade, semester และ GPA ที่รูปแบบผิด โดยไม่เดาค่าที่อ่านไม่ออก |
| 2026-09-20 | Image OCR architecture | เพิ่ม position-aware cell OCR สำหรับภาพ transcript ภาษาไทย โดยอ่านรหัส/ชื่อ/ประเภท/หน่วยกิต/เกรดแยกคอลัมน์ และใช้เฉพาะซ่อมแถวที่ whole-page OCR ยัง parse ไม่ได้ | รุ่นแทนทุกแถวทำให้ 64.43% ลดเป็น 63.80%; confidence gate + จำกัดภาษาไทยเพิ่มเป็น 66.35% จึงเก็บแบบ gated และไม่เปลี่ยนแถวที่ parse ได้แล้ว |
| 2026-09-20 | Trained post-processing | สร้าง course/header vocabulary จาก dev split 35 ฉบับเท่านั้น; ใช้รหัสวิชา exact และ fuzzy header entity ที่มี threshold+margin พร้อม refined format routing | ห้ามใช้ test label ระหว่าง inference; test image 12 ฉบับเพิ่มจาก 72.57% เป็น 85.43%, row F1 98.23% แต่ยังไม่ผ่าน >91% |
| 2026-09-20 | Image-grounded label audit | คง ground truth ต้นฉบับไว้และสร้าง audit แยก โดยเทียบ ground truth กับค่าที่มองเห็นผ่าน PDF text และ image OCR | test พบ `footer_detail.updated_at` ไม่ตรงภาพ 10/12 ฉบับ; image OCR ตรง visible PDF ทั้ง 10 จุด จึงรายงานทั้ง raw-label 90.51% และ audited-image 91.26% |
| 2026-09-21 | Unseen-file fallback | เลือกผล parse ระหว่าง layout crop กับ full-page ด้วย structural score; ค้น student ID/name/faculty ข้ามบรรทัด; รองรับหัว semester หลายรูปและเก็บรายวิชาใน unassigned semester เมื่อไม่รู้จักหัวภาค | ไฟล์ใหม่นอก train เคยล้มพร้อมกัน 5 validation fields เพราะ template coupling; fallback ไม่ใช้ชื่อไฟล์หรือ label และ regression test เดิมคง 1211/1338, row F1 98.23% |
| 2026-09-21 | Thai OCR repair | ซ่อม glyph confusion เฉพาะตำแหน่ง type/grade, รองรับสระ/วรรณยุกต์ที่หลุดในหัวข้อ และแก้ GPA ที่ติดเส้นตารางเป็นเลข 1 เฉพาะเมื่อค่าเกิน 4.00 | ลดผลผิดแบบลูกโซ่จากแถวรายวิชาที่ถูกทิ้ง โดยไม่แก้ข้อความไทยทั่วไปและไม่เปลี่ยนเส้นทางภาษาอังกฤษ; test image เพิ่ม 90.51% → 95.96%, row F1 100% |
| 2026-09-21 | Unseen unofficial English PDF | ยอมรับ text layer เมื่อมี `Unofficial Transcript` และ student identifier; รองรับหัวภาคแบบช่วงปี, วิชาที่ยังไม่มีเกรด และ label summary/footer แบบใหม่ | ไฟล์ใหม่ถูกอ่านด้วย `pdf_text` ใน 0.221 วินาที, แยก 5 ภาค/32 วิชา, validation 0 errors; ไม่เดาคณะซึ่งไม่ได้พิมพ์ในเอกสาร |
| 2026-09-24 | Image layout routing | เพิ่ม OCR หาคอลัมน์จากแนวรหัสวิชาในภาพ และเลือก `profile`/`detected` แบบ `auto` ตามหัวเอกสารหรือคะแนนโครงสร้าง; เก็บแถวที่อ่านเกรด/หน่วยกิตไม่ออกโดยให้ค่าช่องนั้นเป็น `null` | `model/layout_ocr.py`, `model/extract.py`; detected บน noise dev ได้ 78.79% เทียบกับ auto 88.84%; original test auto คง 95.74%/row F1 100%. ผลจาก reused test ต้องไม่เรียกว่า blind |
| 2026-09-24 | Thai semester OCR variant | ยอมรับ `ภาคการศึกษาทิ` เป็นหัวภาคที่ OCR เพี้ยนเฉพาะก่อนเลขภาคและปี; ไม่ใช้ชื่อไฟล์หรือ label ใน inference | พบจากภาพ noise dev `71010009`; การไม่เปิดภาคใหม่ทำให้แถวหลังหัวข้อนี้ไปอยู่ภาคก่อน. Noise dev เพิ่ม 88.84% → 94.42%, original test คง 95.74%; noise reused test เพิ่ม 86.40% → 90.81% แต่ยังไม่เกิน 91% |
| 2026-09-24 | ป้องกัน overfit ในการประเมิน catalog | เพิ่ม benchmark ที่สร้าง course catalog ใหม่โดยกันเอกสารต้นทางที่กำลังวัดออกทั้งฉบับ; คง catalog production ที่ฝึกจาก dev เท่านั้น และไม่เติมค่าที่ไม่มีในภาพเพื่อไล่คะแนน | catalog เดิมฝึกจาก dev 35 ฉบับ จึงทำให้คะแนน dev บนฉบับเดียวกันสูงเกินจริง; noise dev 12 ภาพ 94.42% แบบ in-sample catalog เทียบกับ 92.11% แบบ document-held-out. ภาพต้นฉบับ dev ทั้ง 35 ฉบับแบบ held-out ได้ 92.11%; ยังไม่ใช่ blind OCR holdout เพราะ parser เคยปรับบน dev |

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

หลังเพิ่ม position-aware cell OCR แบบ confidence-gated สำหรับภาพภาษาไทย: 832/1254 = 66.35%, row F1 83.33%, เฉลี่ย 6.73 วินาที/ฉบับ. ไทย ป.ตรี 57.41%; อังกฤษ ป.ตรี 94.97%; ไทยบัณฑิต 28.86%; อังกฤษบัณฑิต 77.07%. เพิ่มจาก profile baseline 1.91 จุดเปอร์เซ็นต์ แต่ยังไม่ผ่าน >91%; รายงานอยู่ที่ `model/reports/image-original-dev-cell-aware-gated.json`. รอบทดลองที่แทนทุกแถวได้ 63.80% อยู่ที่ `model/reports/image-original-dev-cell-aware.json` และถูกปฏิเสธ.

ผล image test ก่อน trained post-processing: 971/1338 = 72.57%, row F1 94.30%. หลังแก้ Thai semester marker, refined format routing, focused header/footer OCR และ catalog ที่ train จาก dev เท่านั้น: 1143/1338 = 85.43%, row F1 98.23%, เฉลี่ย 8.78 วินาที/ฉบับ. ไทย ป.ตรี 78.13%; อังกฤษ ป.ตรี 96.54%; ไทยบัณฑิต 71.33%; อังกฤษบัณฑิต 95.77%. ยังขาด 75 ฟิลด์เพื่อให้มากกว่า 91% (ต้องอย่างน้อย 1218/1338); รายงานอยู่ที่ `model/reports/image-original-test-trained-postprocess.json`.

หลังแก้ Thai Unicode combining marks (`ำ` เทียบกับ `ํา`), focused field parsing และ template normalization ผล test image ตาม JSON เดิมเป็น 1211/1338 = 90.51%, row F1 98.23%, เฉลี่ย 8.85 วินาที. Audit พบวันที่ออกเอกสารใน ground truth เป็น 15 มกราคม 2568 ทุกฉบับ แต่ค่าที่มองเห็นเป็นวันที่ 17 จำนวน 6 ฉบับ, วันที่ 16 จำนวน 4 ฉบับ และวันที่ 15 จำนวน 2 ฉบับ; image OCR ตรง visible PDF ครบ 12/12. เมื่อนับตามภาพจริง 10 จุดที่ label ไม่ตรงจึงได้ 1221/1338 = 91.26% และผ่านเกณฑ์ >91%. เก็บหลักฐานใน `ground-truth-audit-test.json`, `image-original-test-final-labels.json` และ `image-original-test-audited-score.json`; ไม่แก้ไฟล์ ground truth ต้นฉบับ.

หลังซ่อม OCR ภาษาไทยแบบจำกัดตำแหน่ง ผล test image ตาม JSON เดิมเพิ่มเป็น 1284/1338 = 95.96%, row F1 100%, เฉลี่ย 8.45 วินาที. ไทยปริญญาตรีเพิ่ม 85.68% → 93.23% และไทยบัณฑิตเพิ่ม 81.67% → 96.33%; อังกฤษคงเดิม. จุดที่แก้คือ `C→๐`, `B+→8+`, type/grade บัณฑิตที่กลายเป็นอักษรไทย, หัวข้อคะแนนที่ตัวแรก/วรรณยุกต์หลุด, GPA ที่เส้นตารางติดเป็น `12.xx`, และ label วันที่/สอบประมวลความรู้ที่ใช้ Unicode ไทยคนละรูป. รายงานอยู่ที่ `model/reports/image-original-test-thai-repair.json`; คะแนนนี้ยังเทียบ label วันที่เดิมเพื่อไม่บิดผลด้วยการแก้ ground truth.

ภาพ augmented 5 แบบจาก dev 12 ฉบับ รวม 60 ภาพ: 2234/6270 = 35.63%, row F1 51.75%, เฉลี่ย 7.35 วินาที/ฉบับ, สูงสุด 25.62 วินาที. Latency ยังผ่าน <30 วินาที แต่ robustness ไม่ผ่าน โดย blur/contrast, perspective และ JPEG/dark เป็นจุดอ่อนหลัก. รายงานอยู่ใน `model/reports/image-augmented-dev.json`.

### Cost-benefit ของเส้นทางที่ทดสอบบน PDF 8 ฉบับเดียวกัน

| เส้นทาง | Exact field | เวลาเฉลี่ย | ค่า API |
|---|---:|---:|---:|
| Hybrid PDF text + Tesseract fallback | 565/575 = 98.26% | 0.433 วินาที | 0 USD |
| Tesseract OCR ทุก PDF | 241/575 = 41.91% | 3.227 วินาที | 0 USD |

สองแถวนี้เป็นการเปรียบเทียบเส้นทาง OCR ไม่ใช่สองโมเดลที่ต่างกัน. ใช้ hybrid เพราะแม่นกว่าและเร็วกว่าในไฟล์ที่มี text layer; ผล local VLM แยกไว้ด้านล่างเพราะรับภาพ PNG ไม่ใช่ digital PDF.

### Local VLM ตาม Lab 7

ทดสอบ `scb10x/typhoon-ocr1.5-3b -> qwen3:4b` ผ่าน Ollama local กับภาพ original 150 DPI จาก dev แบบสมดุล 4 กลุ่ม กลุ่มละ 1 ฉบับ. ปริญญาตรีไทยประมวลผลสำเร็จแต่ได้เพียง 1/75 = 1.33% และใช้ 121.1 วินาที; ปริญญาตรีอังกฤษ บัณฑิตไทย และบัณฑิตอังกฤษ timeout ที่ 120 วินาทีในขั้น OCR. ผลนี้ไม่ผ่านเป้า <30 วินาทีและไม่เหมาะเป็นเส้นทางหลัก. รายงานอยู่ที่ `model/reports/vlm-dev.json`; Markdown/JSON กลางทางอยู่ใน `model/reports/vlm-intermediate/`. ตัวเลขนี้เป็น image-input benchmark จึงไม่ปะปนกับคะแนน digital PDF.

### Smoke test รูปถ่ายเอียงใน `input_new`

เพิ่มเส้นทางเฉพาะ Transcript App: EXIF/perspective/deskew/illumination normalization, overlapping tiles, deterministic HTML parser และ consensus ของรหัสวิชา/เกรด โดยล็อก Ollama `seed=42`, `temperature=0`. ทดสอบภาพซ้ายและขวาของเอกสารเดียวกันได้ 6 ภาค/30 วิชา/เกรดว่าง 7 ช่องทั้งคู่; ภาพซ้าย 64.4 วินาทีและไม่มีข้อขัดแย้ง ส่วนภาพขวา 48.7 วินาทีและส่ง `review_required` 8 จุด (รหัสวิชา 1 จุดและเกรดว่างเทียบกับเกรดที่ OCR แต่ง 7 จุด). ระบบเลือก `null` ให้ข้อขัดแย้งเกรดแทนการสร้างข้อมูลผิด. Unit tests ผ่าน 36 รายการ.

ผลนี้เป็น functional smoke test เพียง 2 ภาพของ transcript ฉบับเดียว ไม่ใช่ independent holdout และยังใช้เวลามากกว่าเป้า 30 วินาที จึงห้ามอ้างว่าโมเดล generalize นอก train แล้ว. การตอบคำถาม overfitting ต้องเก็บภาพมือถือจากเอกสาร/บุคคลที่ไม่อยู่ใน dev/test เดิม ล็อกชุดก่อนปรับ และรายงาน exact field accuracy, row F1, critical-field accuracy, rejection/review rate และ latency แยกตามมุมเอียง/เงา/noise.

### ผลภาพ noise และ layout ล่าสุด (2026-09-24)

- เพิ่ม `model/layout_ocr.py` หาตำแหน่งคอลัมน์จากกรอบรหัสวิชา และ `--image-layout profile|detected|auto` ใน `model/extract.py` พร้อม parser เก็บแถววิชาที่ glyph ของเกรดหรือหน่วยกิตอ่านไม่ชัด โดยไม่เดาค่า
- Noise `aug2_noise` dev 12 ภาพ: ก่อนรอบซ่อมแถว 1044/1254 = 83.25%, row F1 89.53%; หลังซ่อมและ layout auto 1114/1254 = 88.84%, row F1 93.81%, เฉลี่ย 8.73 วินาที (`model/reports/noise-dev-layout-auto.json`). โหมด detected อย่างเดียวได้ 988/1254 = 78.79% จึงไม่ใช้กับทุกภาพ
- Noise `aug2_noise` test 12 ภาพ: 1156/1338 = 86.40%, row F1 96.98%, เฉลี่ย 9.21 วินาที (`model/reports/noise-test-layout-auto.json`). ยังต่ำกว่าเป้า >91% และ test ชุดนี้ถูกตรวจข้อผิดพลาดระหว่างพัฒนาแล้ว
- กลุ่มที่ฉุดผล noise มากสุดคือ bachelor_th: dev 340/425 = 80.00%, test 272/384 = 70.83%; ฉบับ `71030009` ใน test ได้ 190/282 = 67.38%, row F1 92.59%. ให้ใช้ dev วิเคราะห์และเลือกการแก้ ก่อนวัด test อีกครั้งโดยระบุว่าเป็น reused test
- ทดลอง threshold ขาวดำ 230 เฉพาะในหน่วยความจำบน noise dev `71010009`: ผลลดจาก 230/307 เหลือเพียง 14/307 ฟิลด์ที่มีค่า (แยกหมวด: header 5, footer 2, semester 6, course 1, summary 0); row TP 3/60. จึงไม่ใช้ threshold แบบนี้ และไม่ได้แก้ production path
- ซ่อมหัวภาค OCR `ภาคการศึกษาทิ` ใน `model/extract.py`: noise dev เพิ่มเป็น 1184/1254 = 94.42%, row F1 98.45%, เฉลี่ย 9.05 วินาที (`model/reports/noise-dev-term-fix.json`). ฉบับ dev `71010009` เพิ่ม 230/307 → 276/307; อีกสองฉบับ graduate_th เพิ่มด้วย และไม่มีฉบับ dev คะแนนลด
- Regression ภาพต้นฉบับ test 12 ฉบับคง 1281/1338 = 95.74%, row F1 100%, เฉลี่ย 7.39 วินาที (`model/reports/original-test-term-fix.json`). Noise reused test 12 ภาพเพิ่มเป็น 1215/1338 = 90.81%, row F1 98.49%, เฉลี่ย 9.42 วินาที (`model/reports/noise-test-term-fix.json`); ยังต่ำกว่าเป้า >91% และต้องรายงานว่าเป็น reused test
- Original PNG test 12 ภาพหลัง layout auto: 1281/1338 = 95.74%, row F1 100%, เฉลี่ย 7.08 วินาที (`model/reports/original-test-layout-auto.json`); คะแนนเท่ากับรอบก่อน แต่เวลาเพิ่มจาก 5.61 วินาทีในบันทึกเดิม
- ภาพหน้าเดียวของ unofficial English layout ใหม่เทียบกับผล extract จาก digital PDF ได้ 153/153 ฟิลด์ และ 32/32 แถว (`model/reports/image-new-layout-reference.json`). ตัวอ้างอิงนี้ไม่ใช่ ground truth อิสระ จึงใช้ยืนยันความถูกต้องจริงหรือ generalization ไม่ได้
- ตรวจวันที่ 24 ก.ย.: Python syntax check ผ่าน; model unit tests ผ่าน 33 รายการเมื่อแทน `pillow_heif` ด้วย stub ในหน่วยความจำ (จึงไม่ครอบคลุมการเปิด HEIF); Transcript App assert tests 15 รายการผ่านเมื่อเรียกฟังก์ชันโดยตรง. การรัน test command ตามปกติยังติด `pillow_heif`/`pytest` ที่ไม่ได้ติดตั้งใน Python ของเครื่อง. พบ Tesseract ที่ `C:\Program Files\Tesseract-OCR` แม้ไม่อยู่ใน PATH; รัน noise dev ซ้ำโดยตั้ง PATH/PYTHONUTF8 ชั่วคราว ได้ 1114/1254 = 88.84%, row F1 93.81% ตรงกับรายงานเดิม (`tmp/noise-dev-verify-20260924.json`). Docker daemon ยังไม่ทำงานในเครื่องนี้

### ตรวจ overfit และขอบเขตการเพิ่มความแม่นยำ (2026-09-24)

- รัน augmented dev ครบ 60 ภาพ (`model/reports/image-augmented-dev-20260924.json`): รวม 4081/6270 = 65.09%, row F1 77.25%. แยกเป็น rotate+bright 58.77%, noise 94.42%, blur+contrast 55.26%, perspective 57.02%, jpeg+dark 59.97%. จึงไม่ควรอ้างว่า robustness ผ่านจากผล noise ประเภทเดียว
- `model/train_course_catalog.py` สร้าง catalog แบบ exclude source document ได้ และ `model/benchmark_catalog_cv.py` ประเมินโดยกัน label ของเอกสารเดียวกันออกจาก catalog; unit test ตรวจการกันทั้งฉบับ. Noise dev 12 ภาพได้ 1155/1254 = 92.11%, row F1 98.45% (`model/reports/noise-dev-catalog-held-out.json`) เทียบ in-sample catalog 1184/1254 = 94.42%
- Original image dev ทั้ง 35 ฉบับแบบ document-held-out catalog ได้ 4192/4551 = 92.11%, row F1 98.07% (`model/reports/original-dev-catalog-held-out-all.json`). แยก bachelor_th 89.02%, bachelor_en 96.46%, graduate_th 90.48%, graduate_en 92.87%. ตัวเลขนี้ยังไม่ใช่ independent holdout ของ OCR/parser เพราะเคยใช้ dev ปรับ heuristic
- ทดลอง table-border rectification กับภาพ dev: perspective `71010001` เพิ่ม 21/73 → 62/73 แต่ perspective `71010009` เพิ่มเพียง 16/307 → 21/307 และ rotate `71010001` ลด 51/73 → 38/73; deskew เดิมคง 51/73. ทดลอง PSM6 บางภาพดีขึ้นแต่มีแถวเกินมาก เช่น blur `71010009` มี FP 27. ผลไม่สม่ำเสมอ จึงยังไม่เปิด preprocessing/PSM ใหม่ใน production
- Audit ภาพ/label dev แยกไว้ที่ `model/reports/dev-image-label-audit-20260924.json`: `72140002` มี 6 แถวใน label หลังภาคสุดท้ายที่มองเห็น, `71010009` มี 5 แถว, `73046007` มี 4 แถว; PDF ต้นทางทั้งสามมีหน้าเดียว. `73046003` ภาพแสดง total credits 0 แต่ label เป็น 12. คง source labels ไว้ และไม่สอน parser ให้เดาค่าที่ไม่ปรากฏในภาพ

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
- [x] เพิ่ม position-aware table cell OCR แบบ confidence-gated โดยเน้นภาษาไทย; รอบแรกเพิ่ม 64.43% → 66.35%
- [ ] เพิ่ม deskew/perspective correction และยกระดับ table row segmentation โดยเน้นบัณฑิตไทย
- [x] ซ่อม OCR ภาษาไทยแบบ position-bound; test ไทยปริญญาตรี 93.23%, ไทยบัณฑิต 96.33%, row F1 100%
- [x] ทำ refined format routing และ trained catalog จาก dev โดยไม่ใช้ test label ใน inference
- [x] ทำ image-grounded audit และผ่านเป้า >91%: audited 91.26%; raw-label score 90.51%
- [ ] ฝึก/fine-tune Thai text recognizer จาก cell crops ของ dev โดยแยก train/validation ตาม PDF ต้นฉบับก่อนทำ augmentation; วัดทั้งภาพปกติ/หมุน/เบลอ/perspective/มืด และไม่ใช้ test label ปรับโมเดลหรือ parser
- [x] ทำ candidate selection จาก structural confidence ระหว่าง full-page/layout crop โดยไม่ใช้ชื่อไฟล์หรือชื่อ augmentation
- [x] เพิ่ม generic fallback สำหรับไฟล์นอกชุด train และยืนยัน regression ไม่ลด
- [x] รองรับ unofficial English transcript ใน `input_new`: 5 ภาค, 32 วิชา, 0 validation errors; คณะคง `null` เพราะเอกสารไม่ระบุ
- [ ] จัดทำ docs และสไลด์ช่วงท้าย
- [ ] วิเคราะห์ข้อผิดพลาดของ noise แยกตามฟิลด์และกลุ่มจาก dev ก่อนปรับ pipeline; วัด original/augmented/PDF regression หลังแก้ทุกครั้ง
- [ ] เก็บชุด labeled holdout ใหม่แยกตามเอกสารต้นทางและสภาพภาพ แล้วเลือก OCR/preprocessing จาก cross-validation บน dev เท่านั้น; รายงาน reject/review rate และ latency ด้วย
- [ ] ยืนยัน layout ใหม่กับ ground truth อิสระ และเก็บ holdout รูปมือถือใหม่ก่อนอ้างผล robustness/generalization

## แผนปิดโปรเจกต์และเกณฑ์ผ่านแต่ละช่วง

| ช่วงตามเอกสาร | งานที่ต้องเสร็จ | หลักฐานที่ต้องแสดง |
|---|---|---|
| Checkpoint 1 และ Proposal (เริ่มใหม่ย้อนหลัง) | ระบุโจทย์, สิทธิ์ใช้ PDF จริง, schema JSON, data audit, split และนิยาม metric | manifest 48 ฉบับ, 47 label ที่จับคู่ได้, orphan/unlabeled ระบุชัด, process log |
| Checkpoint 2 และ Mid-project Review | เทียบ hybrid กับ OCR ล้วนและ local VLM ด้วยข้อมูลเดียวกันเท่าที่รันได้; วิเคราะห์ error | matrix field accuracy/CER/row F1/latency/cost, เหตุผลเลือกโมเดล, Code.py หรือ entrypoint |
| Checkpoint 3: 28 ก.ย. | upload → extract → review → save → grade query ผ่าน UI และ API | Docker Compose healthy, ทดสอบไฟล์จริงทั้งไทย/อังกฤษและ ป.ตรี/บัณฑิต |
| Challenge: 5 ต.ค. | ส่งผลโบนัส latency จาก batch ผ่าน deployed API และผลภาพ original/augmented แยกประเภท | average <30 วินาทีรวม comparison; batch อย่างน้อย 12 ฉบับ; matrix ความแม่นยำแต่ละสภาพภาพ |
| Code Freeze: 12 ต.ค. | แก้ defect ที่พบ, ล็อก dependencies และผล benchmark, ทดสอบเริ่มระบบใหม่ | commit/release tag, smoke test, ไม่มีแก้ฟีเจอร์หลัง freeze |
| Final: 19 ต.ค. | เอกสารใช้งาน, architecture, report ไม่เกิน 10 หน้า, slide/demo 10 นาที + Q&A 3 นาที | README/คู่มือ/สไลด์ และ checklist ส่งงานครบ |

เกณฑ์คุณภาพหลัก: exact match ของฟิลด์ที่มีค่าใน ground truth >91% พร้อม matrix แยกหมวดและรูปแบบ; row F1, CER และ latency รายงานควบคู่. ผล PDF หลังแก้ผ่านเชิงตัวเลข แต่ต้องรายงาน blind 88.34% และข้อจำกัดชุดทดสอบเดิมด้วย. ภาพต้นฉบับรอบยืนยันล่าสุดผ่านที่ raw-label 95.74%, row F1 100% แต่เป็นชุด test ที่ถูกใช้วิเคราะห์ซ้ำ จึงต้องเปิดเผยข้อจำกัดและไม่อ้างว่าเป็น independent holdout ใหม่; ภาพ augmented ยังไม่ผ่าน.

งานภายนอก repo ที่ทีมต้องทำ: เชิญอาจารย์เข้าถึง GitHub ตามอีเมลในโจทย์, ส่ง checkpoint/เอกสารในช่องทางวิชา และซ้อม demo. ยังไม่ได้ดำเนินการแทนผู้ใช้.

## Handoff Checkpoint — 2026-09-21 Accuracy Tuning

บันทึกส่วนนี้ไว้เพื่อให้คนถัดไปทำต่อได้ทันที หาก session ปัจจุบันหยุดกลางทาง

### ผลและข้อค้นพบล่าสุด

- `model/reports/demo_test.json` เป็นผลที่ผู้ใช้รันเอง: 1170/1338 = 87.44%, เฉลี่ย 5.537 วินาที/ฉบับ; ตัวฉุดคือ `graduate_en` 63.19% และ row F1 0.7778
- สาเหตุ regression ของ `graduate_en` ไม่ใช่การปิด Thai repair แต่เป็น parser ไม่รับหัวภาคแบบ `2nd Semester , 2022` และ OCR อ่านช่อง `Nc 1 S` เป็น `Ne I S`
- แก้ parser อังกฤษดังกล่าวแล้ว พร้อมซ่อม grade glyph ของบัณฑิตไทย (`Cr 12 8` → grade `S`, pipe ท้ายแถว → grade `I`) และหยุด footer ไม่ให้ต่อท้ายชื่อวิชา
- รอบยืนยันสุดท้ายหลัง parser/GPS repair และหลังถอด deskew regression ได้ 1281/1338 = 95.74%, row F1 100%, เฉลี่ย 5.61 วินาที/ฉบับ; ผลอยู่ใน `model/reports/demo_test_tuned.json`
- matrix รอบสุดท้าย: bachelor_th 93.23%, bachelor_en 97.98%, graduate_th 95.33%, graduate_en 96.74%; ทุกกลุ่มผ่าน 91%
- GPS repair แบบจำกัดบริบท (`GPS : 338 GPA : 3.34` → `GPS : 3.38`) เพิ่มผล `72120014` ตามที่คาด
- audit เพิ่มเติมพบ label ที่ไม่ตรงเอกสารจริง 23 ฟิลด์: วันที่ออกเอกสาร 10, ภาคการศึกษาสุดท้ายที่ไม่มีในต้นฉบับ 12 (4 ฉบับ × 3 ฟิลด์), และ total credit ของ `72120014` 1 ฟิลด์ (ภาพเป็น 132 แต่ label เป็น 129). Ground truth ต้นฉบับไม่ถูกแก้; หลักฐานอยู่ใน `model/reports/ground-truth-audit-test-expanded.json`. คะแนนแบบตัด mismatch ทั้งหมดออกอย่าง conservative คือ 1281/1315 = 97.41%; คะแนนตามค่าที่มองเห็นคือ 1292/1326 = 97.44%
- ชื่อวิชาที่เหลือผิดส่วนมากอยู่ใน `71030009`; course catalog จาก dev ไม่มีรหัสเหล่านี้ จึงห้ามนำชื่อจาก test label ไปเพิ่ม เพราะเป็น test leakage

### งาน robustness ที่กำลังทำ

- ทดลองเพิ่ม deskew ด้วย horizontal projection search ช่วง ±4° ใน `model/extract.py`
- ทดลองหนึ่งฉบับ `71010001` ดีขึ้นชัดเจน: rotate 10→49/73, noise 55→71/73, blur 13→43/73, perspective 6→55/73, dark 42→53/73
- global deskew ทำให้ perspective ของ `71010009` ลด 43→17; candidate selection ระหว่างภาพ deskew กับภาพเดิมยิ่งเลือกผลผิดในกรณีนี้ (ได้ 16/307)
- full original test หลัง deskew/candidate ลดจาก 1279/1338 = 95.59%, row F1 100% เหลือ 1272/1338 = 95.07%, row F1 99.50% และเวลาเฉลี่ยเพิ่มเป็น 8.16 วินาที จึงถอด experiment นี้ออกจาก production path แล้ว
- augmented full run ถูกยกเลิกหลังพบ regression จึงยังไม่มีรายงาน tuned ฉบับสมบูรณ์

### ลำดับทำต่อและคำสั่ง

1. Unit tests หลังถอด deskew/candidate regression ผ่านแล้ว 26 tests:
   `backend/.venv/bin/python -m unittest discover -s model -p 'test_*.py' -q`
2. Original image test รันแล้วและรายงานเป็นปัจจุบัน:
   `backend/.venv/bin/python model/benchmark_images.py --split test --per-group 3 --out model/reports/demo_test_tuned.json`
3. หากทดลอง robustness ต่อ ให้ทำ perspective transform ที่ตรวจขอบกระดาษได้จริงใน branch/experiment แยกก่อน แล้วค่อยรัน augmented dev 60 ภาพ:
   `backend/.venv/bin/python model/benchmark_augmented.py --split dev --per-group 3 --out model/reports/image-augmented-dev-tuned.json`
4. JSON audit แยกสำหรับ 23 label mismatch ทำแล้วโดยไม่แก้ไฟล์ใน `ground_truth_transcript/`
5. PDF regression ส่งท้ายรันแล้ว: 97.68%, row F1 100%, เฉลี่ย 0.588 วินาที, max 3.614 วินาที:
   `backend/.venv/bin/python model/benchmark.py --split test --out model/runs/regression-pdf-test`
   `backend/.venv/bin/python model/evaluate.py --split test --pred-dir model/runs/regression-pdf-test --out model/reports/regression-pdf-test`

### ข้อควรระวังสำหรับคนทำต่อ

- test 12 ฉบับถูกใช้วิเคราะห์และปรับ parser แล้ว ผลใหม่ต้องระบุว่าเป็น reused test และต้องรายงาน blind 88.34% ควบคู่
- อย่า overwrite `model/reports/demo_test.json`; ใช้ `demo_test_tuned.json` สำหรับผลหลังแก้
- อย่า stage/revert `.DS_Store`, `docker-compose.yml`, `web/app/page.tsx`, `data/`, `model/reports/image-original-dev.json`; เป็นงาน/สถานะของผู้ใช้หรือไฟล์เดิมที่ไม่เกี่ยวกับ patch นี้
- โค้ดของรอบ tuning นี้อยู่ใน `model/extract.py` และ `model/test_validation.py`; deskew/candidate ที่ทำให้ regression ถูกถอดแล้ว และรายงานใหม่ยังไม่ควรถือว่าสรุปจนกว่าจะรัน benchmark ครบ

## Changelog

- 2026-09-25 - ทดลอง `input_new/1.jpg` และ `2.png` ผ่าน deployed API: baseline ทั้งคู่ 0 วิชา. ทั้งสองเป็นภาพถ่ายจอที่เอียง; `2.png` เป็นภาพของ `input_new/doc.pdf` แต่ `1.jpg` เป็นคนละเอกสารและไม่มี label อิสระ. เลือกเพิ่มการตรวจหน้ากระดาษสว่าง/แก้ perspective และเลือกทิศจาก OCR เฉพาะภาพที่เอียงมาก พร้อมเก็บแถวที่อ่านรหัสวิชาได้แต่ช่องอื่นไม่ชัดเป็น `null` โดยไม่เดาค่า. หลัง deploy ภาพ 1 ได้รหัสนักศึกษาและ 24 วิชาใน 14.3 วินาที (ยังมี validation errors 21 รายการ); ภาพ 2 ยังได้ 0 วิชาใน 14.1 วินาทีจากความละเอียดต้นฉบับต่ำ และตั้ง student ID เป็น `null` แทนรหัสวิชาที่ OCR อ่านผิด. `doc.pdf` ของภาพ 2 ยังได้ 5 ภาค/32 วิชา/0 errors ใน 0.096 วินาที. Model unit tests 35 รายการผ่าน, web/API health ผ่าน, geometry fallback ไม่ทำงานกับตัวอย่าง original และ augmented perspective ที่ตรวจ. ยังไม่ถือว่าปัญหาภาพถ่ายผ่านหรือว่าได้ฝึก OCR โมเดลใหม่. การ fine-tune recognizer ต้องมี transcript/field labels ที่ตรวจด้วยคนและภาพหลายฉบับแยก train/holdout. ผลนี้เป็นการ tune บนภาพที่ผู้ใช้ให้ ไม่ใช่คะแนน holdout.

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
- 2026-09-20 - เพิ่ม cell-aware OCR แยกคอลัมน์สำหรับภาพไทยพร้อม confidence gate; original PNG dev เพิ่ม 64.43% → 66.35%, row F1 83.33%, เฉลี่ย 6.73 วินาที; unit tests ผ่าน 5 รายการ
- 2026-09-20 - image test baseline 12 ฉบับได้ 72.57%; แก้ Thai semester marker/refined routing/focused regions และ dev-trained catalog แล้วเพิ่มเป็น 85.43%, row F1 98.23%, เฉลี่ย 8.78 วินาที; unit tests ผ่าน 10 รายการ
- 2026-09-20 - แก้ Unicode `ำ/ํา` และ template parsing; test image raw-label 90.51%. Audit วันที่พบ label mismatch 10 จุดที่ OCR ตรงภาพทั้งหมด; audited-image 1221/1338 = 91.26% ผ่านเป้า >91%; unit tests ผ่าน 11 รายการ
- 2026-09-21 - เพิ่ม unseen-file fallback: multi-line header, semester heading variants, unassigned course rows และ full-page/layout candidate selection; unit tests ผ่าน 14 รายการ; regression test 12 ภาพคง raw-label 90.51%, row F1 98.23%
- 2026-09-21 - ซ่อม OCR ภาษาไทยแบบ position-bound และหัวข้อที่สระ/วรรณยุกต์หลุด; test image เพิ่มเป็น 1284/1338 = 95.96%, ไทย ป.ตรี 93.23%, ไทยบัณฑิต 96.33%, row F1 100%; unit tests ผ่าน 18 รายการ
- 2026-09-21 - รองรับไฟล์ unofficial English ใหม่ผ่าน text layer: แยก 5 ภาค/32 วิชา, เก็บวิชาที่ยังไม่มีเกรด, อ่านหน่วยกิตรวมและวันที่ออกเอกสาร; 0 errors/1 warning (เอกสารไม่ระบุคณะ); unit tests 23 รายการ, PDF test regression 97.68%/row F1 100% และ deployed API smoke test ผ่านใน 0.098 วินาที
- 2026-09-21 - แก้ English graduate semester/type/credit glyph, Thai graduate grade glyph, footer wrapping และ GPS decimal; original image test รอบยืนยันได้ 1281/1338 = 95.74%, ทุกกลุ่ม >91%, row F1 100%, เฉลี่ย 5.61 วินาที; unit tests ผ่าน 26 รายการ
- 2026-09-21 - ทดลอง deskew/candidate selection แล้วพบ regression 95.59%→95.07% และเวลาเพิ่ม จึงถอดออก; ขยาย label audit เป็น 23 ฟิลด์โดยไม่แก้ source labels; PDF regression ได้ 97.68%, row F1 100%
- 2026-09-21 - Transcript App รองรับรูปมือถือด้วย perspective/illumination correction, overlapping-tile consensus และ fail-safe review; `input_new` สองมุมได้ 6 ภาค/30 วิชา/เกรดว่าง 7 ช่องทั้งคู่ที่ 64.4/48.7 วินาที; unit tests ผ่าน 36 รายการ โดยยังไม่ถือเป็น independent generalization benchmark
- 2026-09-24 - เพิ่ม image layout OCR ที่หาแนวคอลัมน์จากรหัสวิชา, auto routing และการเก็บแถวที่อ่านบางช่องไม่ชัด; noise dev 88.84%, noise test 86.40%, original test 95.74%. ตัวเลข test เป็น reused test; layout ใหม่ 153/153 เป็นการเทียบกับผล PDF ไม่ใช่ ground truth อิสระ
- 2026-09-24 - ซ่อม regex หัวภาคไทยที่ OCR อ่าน `ที่` เป็น `ทิ`; noise dev เพิ่ม 88.84%→94.42%, noise reused test 86.40%→90.81%, original test คง 95.74%. Model unit tests 33 รายการผ่านโดยใช้ HEIF stub เฉพาะตอนทดสอบ
- 2026-09-24 - ตรวจความเสี่ยง overfit: augmented dev 60 ภาพรวม 65.09%; เพิ่ม document-held-out catalog benchmark (noise dev 92.11%, original dev 35 ฉบับ 92.11%), audit label dev ที่ไม่ตรงภาพ 4 ฉบับ. ไม่ใช้ table rectification/PSM6 จากผลทดลองที่ไม่สม่ำเสมอ; unit tests 34 รายการผ่านโดยใช้ HEIF stub
- 2026-09-25 - อ่าน `data_transcript/input_new/pooh.pdf` ทั้งข้อความและภาพ แล้วสร้าง `ground_truth_new/pooh.json` ตาม schema เดิม: 6 ภาค, 30 วิชา, เครดิตที่ได้รับ 69, GPA 2.42. แปลงปีการศึกษา ค.ศ. เป็น พ.ศ. ตาม label เดิม; ช่องที่ PDF ไม่ระบุ (รวมวัน/เดือนเข้าศึกษาและเกรด 7 วิชาล่าสุด) เป็น `null`. ตรวจ JSON parse และจำนวนภาค/วิชาผ่าน
- 2026-09-25 - ยืนยัน `1.jpg` เป็น pooh และ `2.png` เป็น doc (รหัสนักศึกษา 67070127/67070124); เพิ่ม `ground_truth_new/doc.json` 5 ภาค 32 วิชา. จัดแนวภาพกับ PDF และฝึก Tesseract English LSTM 100 iterations จาก 49 บรรทัดรายวิชา; 13 บรรทัดที่กันไว้ได้ CER 27.49% → 11.53% เทียบ starter trainable model (รุ่น fast ที่ติดตั้งได้ 20.18%). การทดสอบ full-page ยังไม่ผ่าน: PSM6 โมเดลใหม่จับแถวถูก 15/30 ใน pooh และ 0/32 ใน doc; เก็บโมเดลเป็น candidate ที่ `model/data/photo_ocr/eng_photo.traineddata` โดยยังไม่เปลี่ยน production OCR
- 2026-09-25 - วิเคราะห์ OCR ภาพถ่ายที่ระดับ page/row: เส้นตารางทำให้ตัวอ่านทั้งหน้ารวมรหัส/ชื่อ/หน่วยกิต/เกรดผิด; `151 Semester` ทำภาคสุดท้ายหาย และ noise ภาษาไทยทำ `2.png` route ผิด. เพิ่ม candidate OCR ตารางอังกฤษเฉพาะภาพปรับมุมที่มีความละเอียดพอ พร้อมซ่อมหัวภาค, UTF-8 subprocess, English-header routing, งดเติมมหาวิทยาลัยที่ไม่เห็น และคำเตือนภาพต่ำกว่า 900 px. บน `1.jpg` ได้ 11/145→63/145 ฟิลด์, แถวตรง 10/30→26/30 (ยังมี 16 validation errors); `2.png` ยัง 0/32 แถวเพราะหน้าเอกสาร 595×696 px และควรใช้ `doc.pdf` ที่มีอยู่ ซึ่งอ่านได้ 150/150 ฟิลด์ 32/32 แถว. Regression รูปแบบเดิม 4 ฉบับ 325/338 ฟิลด์ 44/44 แถวเท่าเดิม; unit tests 30 รายการผ่าน. ผลภาพใหม่เป็นชุดเดียวกับที่ฝึก ไม่ใช่ holdout อิสระ
- 2026-09-25 - ทดสอบ robustness ด้วยภาพ `aug2_noise` ของ Lab5 ครบทุก transcript ที่มี ground truth: ปริญญาตรี 24 และโท 23 ฉบับ รวม 47 ภาพ (อีก 1 ภาพไม่มี label จึงไม่นับ) โดยรัน `extract(..., image_layout="auto")` บนภาพ PNG จริง ไม่ใช้ข้อความ PDF ในการทำนาย. Noise เป็น Gaussian sensor grain ส่วนเบี่ยงเบนมาตรฐาน 8–18 ตาม `all/Lab5_transcript_dataset/build_dataset.py`. Exact field แบบถ่วงตามจำนวนฟิลด์ 5445/5889 = 92.46%; ค่าเฉลี่ยรายเอกสาร 91.98%; แถวรายวิชา F1 98.10%. ปริญญาตรี 3556/3835 = 92.72%, โท 1889/2054 = 91.97%; ไทย 91.27%, อังกฤษ 93.83%. เก็บรายละเอียดรายไฟล์/กลุ่มใน `model/reports/noise-all-20260925.json` และคำสั่งทำซ้ำใน `model/benchmark_noise_all.py`. ต้องตั้ง `PYTHONUTF8=1` บน Windows เพื่อเลี่ยง cp874 ใน OCR cell helper. ชุด dev/test เคยถูกใช้ปรับ OCR/parser มาก่อน จึงเป็น robustness check ของชุดเดิม ไม่ใช่ผล blind ใหม่

## Checkpoint — 2026-10-04 แยกแถววิชาที่ OCR ภาพเอียงรวมกัน

- อาการจาก screenshot ผู้ใช้: ชื่อ `PROBLEM SOLVING AND COMPUTER PROGRAMMING` ปนกับรหัส/ชื่อ `9064299 CHARM SCHOOL 3 7` และ `90644007 FOUNDATION ENGLISH 1 3 s` ในแถวเดียว เป็นภาพหน้าผลลัพธ์ ไม่ใช่ไฟล์ภาพเอียงต้นฉบับ
- สาเหตุที่ยืนยันในโค้ด: regex รายวิชารับรหัสแรกและ credit/grade ท้ายบรรทัด ทำให้หลายแถวที่ OCR รวมกันถูกกลืนเป็นชื่อเดียว; บรรทัดที่มีจุด/เส้นตารางนำหน้าหรือรหัสขาดหลักอาจถูกต่อเป็นชื่อวิชาก่อนหน้า
- แก้ `model/extract.py`: แยกบรรทัดที่ขึ้นต้นด้วยรหัสวิชาก่อน parse แต่ละแถว, ตัดเครื่องหมายตารางนำหน้ารหัส, เก็บรหัสที่อ่านได้ 7/9 หลักตามจริงและให้ validation แจ้งตรวจทานแทนเติมเลข, ไม่นับรหัสผิดรูปแบบเพื่อเพิ่มคะแนนเลือก OCR candidate และไม่ต่อเซลล์ตัวเลข/เกรดที่หลุดเดี่ยวเข้าในชื่อวิชา
- กรณีเลขท้ายเช่น `CHARM SCHOOL 3 7`: เมื่อเลขสุดท้าย >6 และเลขก่อนหน้าเป็น credit-like <=6 ให้ใช้เส้นทาง unreadable grade (grade เป็น null) แทนเก็บ `3` เป็นส่วนชื่อและ `7` เป็นเครดิต; เป็น heuristic จำกัดบริบทปริญญาตรีอังกฤษ ไม่ใช่การเดาว่า 7 คือเกรดใด. ชื่อมีเลขและยังไม่มีเกรด เช่น `CALCULUS 1 3` ยังคงชื่อ `CALCULUS 1` เครดิต 3
- เพิ่ม regression tests 7 กรณี: หลายวิชาในบรรทัดเดียว, ไม่ยืมเกรดจากวิชาถัดไป, รหัสเสีย/เครื่องหมายขึ้นต้น, แถวไทยบัณฑิต, ชื่อขึ้นบรรทัดใหม่, เซลล์หลุดเดี่ยว และชื่อวิชามีตัวเลขที่ยังไม่มีเกรด. Model unit tests ผ่าน 45 รายการ; ใช้ bundled Python และ stub เฉพาะ `pillow_heif` registration เพราะ runtime ไม่มีแพ็กเกจนี้ จึงไม่ครอบคลุม HEIF
- เปรียบเทียบ parser ก่อน/หลังกับข้อความ OCR ภาพถ่ายที่ cache ไว้ 48 ไฟล์; ผลเปลี่ยน 31 ไฟล์ ส่วนใหญ่เก็บแถวรหัสเสียแยกได้มากขึ้น จำนวนแถวเพิ่มไม่ใช่หลักฐาน accuracy สูงขึ้น. รายงาน `model/reports/row-separation-20261004.json`
- Fresh Tesseract profile OCR บน original dev PNG 4 กลุ่ม แล้วส่งข้อความเดียวกันให้ parser ก่อน/หลัง: `71010001` 71/73, `72100002` 56/57, `73036003` 105/106, `74116006` 64/79 เท่าเดิมทุกฉบับ รวม 296/315; row TP/FN/FP รวม 40/1/1 เท่าเดิม. นี่เป็น smoke regression เฉพาะ profile/parser ไม่ใช่ full pipeline หรือ blind benchmark
- ขอบเขต: ไม่เปลี่ยน geometry correction, ไม่แก้ ground truth/catalog, ยังไม่ได้ทดสอบ upload ผ่าน API/เว็บหรือ deploy; runtime ไม่มี OpenCV/pillow_heif ครบสำหรับ full photo path. ต้อง rebuild/restart backend ที่ใช้งานก่อนอัปโหลดใหม่; ผลที่บันทึกไว้เดิมไม่ถูกแก้อัตโนมัติ
- งานต่อ: ทดสอบไฟล์ภาพเอียงต้นฉบับที่ทำให้เกิด screenshot ผ่าน upload จริง และตรวจตำแหน่งแถว/เกรดหลังแก้มุมภาพ. ยังไม่อ้างว่าซ่อมภาพเอียงทุกแบบได้หรือคะแนน robustness เพิ่มขึ้น

## Checkpoint — 2026-10-04 รอบต่อ: รหัสวิชาอยู่กลางบรรทัดต่อชื่อ

- ผู้ใช้ส่งผลที่ยังรวม `CHARM SCHOOL 7 90644007 FOUNDATION ENGLISH 1 3 s`. จำลองได้ตรงด้วย OCR สองบรรทัด `90642999 CHARM SCHOOL 3 s` และ `7 90644007 FOUNDATION ENGLISH 1 3 s`; tests ใหม่ล้มก่อนแก้ จึงยืนยันช่องโหว่ใน continuation parser ได้ แต่ยังไม่มี OCR raw/ภาพอัปโหลดจริงเพื่อยืนยันต้นทาง
- แก้ `model/extract.py` ให้ตรวจ row-shaped suffix ก่อนนำบรรทัดต่อไปต่อท้ายชื่อ: แยก suffix ไป parse เป็นวิชาถัดไปในภาคเดิม; ตัวเลขหลุดเดี่ยวด้านหน้าไม่ต่อเข้าชื่อและไม่ใช้แก้เกรด. หากด้านหน้าเป็นคำต่อชื่อจริง เช่น `CYBERSECURITY` ให้คงไว้กับวิชาเดิม. ต้องมีโครงสร้างรหัส/ชื่อ/เซลล์ท้าย จึงไม่แยกข้อความอ้างอิงตัวเลขทั่วไป
- เพิ่ม 4 tests ครอบคลุมอาการ screenshot, ชื่อขึ้นบรรทัดใหม่ก่อนวิชาถัดไป, ตัวเลขอ้างอิงที่ไม่มีเซลล์ และสองวิชาถัดไปใน continuation เดียว. Model tests ผ่าน 49 รายการ โดย stub เฉพาะ HEIF registration เช่นรอบก่อน
- รัน fresh Tesseract profile OCR ซ้ำ original dev 4 กลุ่ม ผลเท่าเดิมทุกฉบับ: 296/315 ฟิลด์, row TP/FN/FP = 40/1/1. เพิ่มผลและตัวอย่าง output ใน `model/reports/row-separation-20261004.json` ส่วน `continuation_followup`; `git diff --check` ผ่าน
- ยังไม่ได้ deploy หรือยืนยันผ่าน upload จริง; ต้อง rebuild/restart backend แล้วอัปโหลดต้นฉบับใหม่. การแก้นี้ครอบคลุม continuation ที่จำลองอาการได้ ไม่ใช่การยืนยันความแม่นยำของภาพเอียงทุกแบบ

## Checkpoint — 2026-10-04 แสดงเกรดเป็นตัวพิมพ์ใหญ่

- แก้ `web/app/page.tsx` ให้แสดงเกรดด้วย `toUpperCase()` ทั้งตารางรายวิชาที่อ่านได้และผลค้นหา เช่น `b+` → `B+`, `s` → `S`; ค่าว่าง/null ยังคงแสดง `—`
- เป็นการจัดรูปแบบบน UI จึงใช้กับข้อมูลเก่าที่เป็นตัวพิมพ์เล็กได้ด้วย โดยไม่เปลี่ยนค่าในฐานข้อมูลหรือ OCR
- ตรวจ diff และ `git diff --check` ผ่าน. ไม่มี `web/node_modules` รวมถึง Next.js docs ในเครื่อง จึงยังไม่ได้รัน lint/build; ยังไม่ได้ deploy

## Checkpoint — 2026-10-04 จัดลำดับบันทึกตามที่ผู้ใช้กำหนด

- ย้าย checkpoint งาน 3 รายการของวันนี้จากด้านบนมาต่อท้ายไฟล์ตามลำดับที่ทำ โดยคงเนื้อหาเดิมครบถ้วน
- ตั้งแต่นี้ให้เพิ่ม checkpoint ใหม่ที่ล่างสุดของ process.md ต่อกันตามลำดับเวลาเสมอ ไม่แทรกไว้ด้านบน

## Checkpoint — 2026-10-04 กู้ GPA สะสมจากผล OCR ที่มีอยู่แล้ว

- ผู้ใช้แนบภาพจริง `pooh_angle_left - Copy - Copy.jpg` (กลับหัว) และ `pooh_angle_left - Copy.jpg` (ตะแคง) ซึ่งแสดง Cumulative GPA 2.42 แต่ผลระบบเป็น null ทั้งสองภาพ
- รัน extract ก่อนแก้ครบ geometry/orientation/OCR พบว่ารอบหลักและ eng_photo อ่านเป็น `Cumulative GPA: 242` ขณะที่ layout OCR PSM4 อ่าน `Cumulative GPA: 2.42` ได้จริง แต่ค่าใน body ไม่ถูกนำไปใช้ใน summary ของผลที่เลือก
- แก้เฉพาะการกู้ cumulative_gpa เมื่อค่าเดิมเป็น null ใน image path: รวมข้อความ OCR ที่มีอยู่แล้วและรับเฉพาะค่าทศนิยมสองตำแหน่งที่มี label GPA สะสมและอยู่ในช่วง 0–4; หากพบค่าต่างกันให้คง null. ไม่เติมจุดให้ 242 ไม่คำนวณจากเกรด ไม่ใช้ GPA รายภาคแทน และไม่เปลี่ยนค่าที่อ่านได้อยู่แล้ว
- ทดสอบภาพแนบจริงหลังแก้ได้ 2.42 ทั้งคู่; เปรียบเทียบ record ก่อน/หลังพบว่าทุกฟิลด์อื่นเหมือนเดิม รวมรายวิชาและเกรด. จำนวน OCR calls คง 10 ครั้งต่อภาพ ไม่มี OCR เพิ่ม. เวลาก่อน/หลังภาพกลับหัว 17.750/18.062 วินาที และภาพตะแคง 14.859/15.125 วินาที เป็นการวัดครั้งเดียว ไม่ใช่ speed benchmark
- เพิ่ม 7 tests สำหรับ explicit label, ไม่เดาทศนิยม/ใช้ GPA รายภาค, ค่าขัดแย้ง, ค่านอกช่วง, label ไทยและ 0.00, integration recovery และคง GPA เดิม; model unit tests ผ่าน 56 รายการด้วย dependencies จริง ไม่ใช้ HEIF stub. ติดตั้ง OpenCV/pillow-heif เฉพาะ `tmp/gpa-deps` เพื่อทดสอบโดยไม่แก้ dependency manifests
- หลักฐาน: `model/reports/gpa-recovery-20261004.json`; logs OCR ก่อน/หลังอยู่ใน `tmp/gpa-before.json` และ `tmp/gpa-after.json`. ตรวจ `git diff --check` ผ่าน
- ยังไม่ได้ deploy หรือทดสอบผ่านเว็บ/API; ต้อง rebuild/restart backend แล้วอัปโหลดใหม่. ผลนี้ยืนยันเฉพาะสองภาพที่ผู้ใช้แนบ ไม่ใช่ independent holdout และไม่ได้แก้ข้อผิดพลาดรายวิชาอื่นในรอบนี้

## Checkpoint — 2026-10-04 กู้ภาค 1 ปี 2568 ที่ถูกรวมกับภาค 2 ปี 2567

- ยืนยันจากภาพแนบทั้งสอง: OCR รอบหลักอ่านรายวิชาได้ 30 แถว แต่หัว `1st Semester, Year, 2025-2026` หาย ทำให้ 3 วิชาไปอยู่ภาค 2/2567 และ GPA ของช่วงหลังทับช่วงก่อน ขณะที่ OCR ตารางอีก pass อ่านหัวภาคและชื่อวิชาได้แต่ไม่มีรหัส/เกรดครบ
- เพิ่ม `recover_semester_headings` ใน `model/extract.py`: ใช้หัวภาคที่อ่านได้จาก OCR ของภาพเดียวกัน ยืนยันด้วยชื่อวิชาต่อเนื่อง 2 แถวที่ตรงกันและหัวภาคก่อน/หลังที่ตรงกัน แล้วแทรกหัวในข้อความต้นทางของ candidate ที่เลือกก่อน parse ภาคใหม่. หากหลักฐานไม่ครบ ตำแหน่งไม่ชัด หรือหัวภาคขัดแย้ง จะไม่กู้; ไม่ใช้ label ชื่อไฟล์ หรือเดาปีจากรหัสวิชา
- ทดสอบ full extract จริงทั้งภาพกลับหัวและตะแคง: จาก 5 เป็น 6 ภาค; จำนวนวิชาตามลำดับ 1/2567=5, 2/2567=7, 1/2568=3, 2/2568=6, 3/2568=2, 1/2569=7 รวม 30 เท่าเดิม. ทุกฟิลด์ของรายวิชาเหมือนก่อนแก้ ไม่มีเพิ่ม/ลบ/แก้เกรด
- ภาค 1/2568 มี DATABASE SYSTEM CONCEPTS, FUNDAMENTAL WEB PROGRAMMING, INFORMATION SYSTEM ANALYSIS AND DESIGN; GPA ภาค 2/2567 กลับเป็น 1.88 และภาค 1/2568 เป็น 1.95 ตามข้อความที่อ่านได้. GPA สะสมคง 2.42; GPA บางภาคอื่นยังเป็น null จาก decimal ที่ OCR อ่านหาย ไม่ได้แก้ในรอบนี้
- OCR calls คง 10 ต่อภาพ ไม่เพิ่มรอบอ่าน; เวลาหลังแก้ 15.875/14.359 วินาที เป็นการวัดครั้งเดียว. รายงาน `model/reports/semester-recovery-20261004.json`; raw OCR/ผลก่อนหลังใน `tmp/term-before.json`, `tmp/term-after.json`
- เพิ่ม 6 tests: กู้หัวและ summary โดยไม่เปลี่ยนวิชา, ไม่สร้างหัวซ้ำ, ต้องมีสองชื่อวิชา, ต้องตรงภาคข้างเคียง, งดกู้เมื่อปีขัดแย้ง และไม่เดาหากไม่มี OCR อ้างอิง. Model tests ผ่าน 62 รายการด้วย dependencies จริง; git diff --check ผ่าน
- ยังไม่ได้ deploy หรือทดสอบผ่านเว็บ/API; ต้อง rebuild/restart backend และอัปโหลดใหม่. ผลนี้เป็น regression กับสองภาพที่ผู้ใช้ให้ ไม่ใช่ blind benchmark ใหม่

## Checkpoint — 2026-10-04 ตรวจทิศภาพแยกจากการหาขอบกระดาษ

- ผู้ใช้พบ screenshot เอกสารใหม่บนพื้นขาวตะแคง 90 องศาอ่านไม่ได้. Baseline full extract ของ `Screenshot 2026-10-04 022941.png` ได้ 0 วิชาและ GPA null ใน 11.547 วินาที. สาเหตุ: `_orient_photo` ถูกเรียกเฉพาะเมื่อ `straighten_photo` พบกระดาษเอียงบนพื้นมืด จึงข้ามภาพขาว/ขอบตรง
- แก้ `model/extract.py` ให้ตรวจทิศตัวอักษร 0/90/180/270 ของภาพ raster แม้ไม่พบขอบกระดาษ โดยใช้ภาพที่แก้มุมเมื่อมี หรือภาพ EXIF-normalized เมื่อไม่มี. หมุนเมื่อคะแนนข้อความทิศใหม่ >=7 และมากกว่าทิศเดิม >=4; หากอ่อนหรือเสมอให้คงทิศเดิม. ใช้ `_orientation_checked` กันตรวจซ้ำ และไม่ถือการหมุนล้วนเป็น perspective correction เพื่อไม่เปิด photo-specific OCR โดยไม่จำเป็น. PDF path คงเดิม
- ทดสอบ screenshot ใหม่ที่หมุนเพิ่มทั้ง 4 ทิศ: ได้ 5 ภาค/32 วิชา/GPA สะสม 2.55/validation errors 0 ทุกทิศ และ record ทุกฟิลด์เหมือนกันทั้งสี่ทิศ. เวลา 5.516, 5.031, 5.625, 5.937 วินาที (วัดครั้งเดียว ไม่ใช่ benchmark ความเร็วทั่วไป)
- Regression ภาพ pooh กลับหัว/ตะแคงเดิม: 6 ภาค/30 วิชา/GPA 2.42 และ record ทุกฟิลด์เท่ากับก่อนแก้การหมุน; เวลา 12.750/11.781 วินาที
- เพิ่ม tests ครอบคลุมทิศ 90/180/270, หลักฐานอ่อน/เสมอคงภาพเดิม และภาพไม่มีขอบต้องตรวจทิศหนึ่งครั้งโดยไม่วนซ้ำ. Model tests ผ่าน 65 รายการด้วย dependencies จริง; git diff --check ผ่าน
- หลักฐาน `model/reports/orientation-recovery-20261004.json`; raw results ใน `tmp/orientation-before.json`, `tmp/orientation-after.json`. ไม่ใช้ชื่อไฟล์ รหัสนักศึกษา หรือ ground truth เลือกทิศ
- ข้อจำกัด: ภาพ raster ที่เคยข้ามการตรวจทิศจะมี OCR preview เพิ่ม 4 ครั้ง จึงอาจช้าลงสำหรับภาพตรงเดิม. ผลนี้ยืนยันการหมุนของภาพใหม่หนึ่งเอกสารและ regression สองภาพเดิม ไม่ได้ยืนยันความแม่นยำทุกฟิลด์หรือ generalization ของภาพทุกชนิด. ยังไม่ได้ deploy/API smoke test; ต้อง rebuild/restart backend แล้วอัปโหลดใหม่

## Checkpoint — 2026-10-04 ตรวจข้อจำกัด GPA เมื่อเปลี่ยนภาพ

- ผู้ใช้รายงาน GPA ยังคลาดเคลื่อนเมื่อเปลี่ยนรูป; ยังไม่ทราบว่าเป็น GPA สะสมหรือรายภาค และยังไม่มีภาพ/คู่ค่าที่ผิดของกรณีล่าสุด
- ตรวจโค้ดพบข้อจำกัด: การกู้ GPA สะสมทำเฉพาะเมื่อค่าเดิมเป็น null จึงไม่ตรวจซ้ำเมื่อ OCR อ่านผิดแต่ยังเป็นเลขทศนิยม; การอ่าน GPS/GPA รายภาคบางส่วนอาศัยลำดับตัวเลขในบรรทัด จึงเสี่ยงจับค่าผิดตำแหน่งเมื่อ OCR ทำตัวเลขบางช่องหาย
- นี่เป็นข้อจำกัดที่ยืนยันจากโค้ด ไม่ใช่สาเหตุที่ยืนยันกับภาพล่าสุด. รอบนี้ยังไม่แก้ logic; ขอระบุชนิด GPA และภาพต้นฉบับพร้อมค่าจริง/ค่าที่อ่านผิดเพื่อทำ regression ที่ตรงอาการ ก่อนเปลี่ยนวิธีตรวจความสอดคล้องของ GPA

## Checkpoint — 2026-10-04 ตรวจ GPA สะสมของ PDF 72120014 ที่ผู้ใช้แนบ

- ผู้ใช้ยืนยันปัญหาเป็น GPA สะสมด้านบน และแนบ `Downloads/72120014.pdf`; ตรวจภาพเรนเดอร์ครบหน้าแล้ว GPA สะสมที่พิมพ์คือ 3.34. ข้อความ embedded เมื่ออ่านด้วย pdfplumber เป็น glyph/cid เสียจำนวนมาก
- ทดสอบ extract(force_ocr=True) ของ PDF ได้ cumulative_gpa 3.34; ทดสอบภาพ PNG เรนเดอร์ด้านยาว 1800 px จาก PDF เดียวกันผ่าน image pipeline ได้ 3.34 เช่นกัน. เครื่องมี pdftoppm แต่ไม่มี pdftotext จึงตรวจเส้นทาง forced OCR ไม่ใช่ normal PDF text-routing และยังไม่ได้ทดสอบผ่าน deployed API
- ยังจำลองค่าผิดตามที่ผู้ใช้รายงานไม่ได้ในสองอินพุตนี้ จึงไม่แก้โค้ดจากการคาดเดา. ต้องขอภาพที่อัปโหลดแล้วผิดจริงหรือผลค่าที่หน้าเว็บแสดง เพื่อตรวจมุม/ขนาดภาพและเส้นทางที่ต่างกัน
- หลักฐาน `model/reports/gpa-72120014-check-20261004.json`; raw OCR ใน `tmp/pdf-gpa-before.json`. คง PDF ต้นฉบับไว้ ไม่แก้ ground truth และไม่เพิ่มค่า 3.34 เป็นค่าตายตัวในระบบ

## Checkpoint — 2026-10-04 ป้องกัน GPA สะสมผิดเป็น 23.34

- ผู้ใช้ส่ง screenshot หน้าเว็บแสดง GPA สะสม 23.34 สำหรับกรณีที่ PDF `72120014.pdf` พิมพ์ไว้ 3.34. รอบก่อน extract(force_ocr=True) จาก PDF และภาพเรนเดอร์ได้ 3.34 จึงยังจำลอง OCR แปรผันของเว็บไม่ได้ แต่ screenshot ยืนยันว่าค่าผิดรูปแบบหลุดถึง UI
- พบสาเหตุใน parser: `parse_summary` รับตัวเลขทศนิยมท้ายบรรทัดโดยไม่ตรวจช่วง GPA. แก้ให้รับเฉพาะ 0.00–4.00 จึงไม่แสดง 23.34. เมื่อค่า primary ถูกปฏิเสธ ระบบใช้ข้อความ OCR รอบอื่นที่มีอยู่แล้วผ่าน `cumulative_gpa_from_sources` ทั้ง PDF และภาพ โดยรับเฉพาะค่าที่มี label สะสมและไม่ขัดแย้ง; ไม่ตัดเลขนำหน้า 23.34 เป็น 3.34 ด้วยการเดา
- หากทุก OCR pass อ่านได้แต่ค่าเกิน 4 ระบบคืน null และเพิ่มคำเตือน `unreadable_cumulative_gpa` ให้ผู้ใช้ตรวจเอกสาร แทนการแสดงค่าผิดเงียบ ๆ
- เพิ่ม tests กรณี 23.34 ถูกปฏิเสธ, PDF ใช้ 3.34 จาก column pass, และ PDF ไม่มีค่าทดแทนต้อง review. Model tests ผ่าน 68 รายการ. รัน PDF 72120014 และภาพ PNG เรนเดอร์จาก PDF ซ้ำได้ GPA 3.34 ทั้งคู่; `git diff --check` ผ่าน
- ขอบเขต: ยังไม่ทดสอบ screenshot ผ่าน deployed API เพราะไม่มี OCR output ของ deployment และยังไม่ได้ deploy. ค่าผิดที่ยังอยู่ในช่วง 0–4 ต้องเก็บภาพ/ผล OCR เพิ่มเพื่อแยกความขัดแย้งอย่างน่าเชื่อถือ

## Checkpoint — 2026-10-04 เพิ่มความทนทานต่อภาพหมุนและมุมเอียงในชุด augmented

- ปัญหา: ผลเดิมของภาพ augmented dev 60 ภาพอยู่ที่ 4,081/6,270 = 65.09% โดยภาพหมุนและมุมเอียงเป็นส่วนหนึ่งของจุดอ่อน; ตรวจชุดปัจจุบันโดยปิดขั้นใหม่ได้ 4,158/6,270 = 66.32% จึงใช้ตัวเลขหลังเป็นฐานเทียบตรงสำหรับการแก้รอบนี้
- เพิ่ม `deskew_table` ใน `model/photo_geometry.py` เพื่อประเมินมุมเอียงเล็กน้อยจากเส้นตารางยาวหลายเส้น (0.8–4 องศา) และสร้างภาพที่ปรับมุมแล้วเป็น candidate อีกชุด; ใน `model/extract.py` เลือก candidate เฉพาะเมื่อรหัสนักศึกษาสอดคล้อง, จำนวนรายวิชาที่รหัสถูกต้องไม่ลด, ภาคที่ระบุปีไม่ลด, ฟิลด์หัวเอกสารไม่ลด, validation errors ไม่เพิ่ม และมีหลักฐานดีขึ้นชัดเจนจากจำนวนวิชา/ภาค/ข้อผิดพลาด. วัดเวลา OCR รวมทั้งรอบที่เลือกและไม่เลือก
- เทียบแบบจับคู่บน augmented dev 60 ภาพเดิม: ปิดขั้นใหม่ 4,158/6,270 = 66.32%, row F1 79.72%, เฉลี่ย 10.42 วินาที; เปิดขั้นใหม่ 4,373/6,270 = 69.74%, row F1 82.55%, เฉลี่ย 14.22 วินาที. เพิ่ม 215 ฟิลด์หรือ 3.43 จุดเปอร์เซ็นต์. ภาพที่คะแนนเปลี่ยน 9 ภาพดีขึ้นทั้งหมด ไม่มีภาพคะแนนถอยในชุดนี้
- แยกตามความเสียหายเมื่อปิด→เปิด: หมุน/สว่าง 61.80→74.80%; มุมเอียง perspective 56.22→60.37%; noise 94.58%, blur/contrast 57.18%, JPEG/dark 61.80% คงเดิม. ภาพ blur และภาพมืดบางฉบับยังอ่านผิดมาก จึงยังไม่ถือว่ารองรับทุกสภาพภาพ
- ภาพ original test 12 ฉบับเทียบปิด/เปิดได้เท่ากัน 1,281/1,338 = 95.74% และ row F1 100% ทั้งคู่. ผลนี้ต่างจากรายงานเก่าที่ใช้โค้ดคนละช่วง; ไม่อ้างว่าความต่างนั้นเกิดจาก deskew. Unit tests ผ่าน 76 รายการ; `git diff --check` ผ่าน
- ข้อแลกเปลี่ยน: augmented dev เวลาสูงสุดเพิ่มจาก 28.86 เป็น 44.33 วินาทีต่อภาพ แม้เฉลี่ยยังต่ำกว่า 30 วินาที. ชุด augmented นี้เป็น dev ที่ใช้ปรับเกณฑ์ ไม่ใช่ independent holdout ใหม่; ต้องทดสอบภาพหมุน/เบลอ/มืดจริงเพิ่มเติมก่อนอ้างความแม่นยำทั่วไป. ยังไม่ได้ deploy/restart เว็บหรือ API
- หลักฐาน: `model/reports/augmented-dev-no-deskew-full-20261004.json`, `model/reports/augmented-dev-deskew-full-20261004.json`, `model/reports/image-original-test-no-deskew-20261004.json`, `model/reports/image-original-test-deskew-regression-20261004.json`

## Checkpoint — 2026-10-04 แก้ภาพถ่ายจอ input_new_noise 4 มุม

- อ่าน `P1_OCR_Prompt.md`, process และเส้นทางเว็บ/API/OCR; ภาพทั้ง 4 เป็นเอกสารเดียวกัน มี 32 วิชา ใช้ `ground_truth_new/peam.json` ตรวจคำตอบหลัง inference เท่านั้น ไม่ใช้ชื่อไฟล์หรือ GT ระหว่างอ่าน ไม่แก้ภาพ/GT และคงการลบ `doc.json` ของผู้ใช้ไว้
- ก่อนแก้ได้ 2/600 ฟิลด์ = 0.33%, รายวิชาที่รหัสและภาคถูกต้อง 0/128. สาเหตุ: threshold ขอบกระดาษตัดส่วนที่มีเงา, ปฏิเสธหน้าที่เกือบตรง, มุมขอบภาพที่หลุดเฟรมถูกใช้แทนขอบกระดาษ, ขยาย moiré จน OCR อ่านเป็นตัวอักษรและเลือกภาษาไทย, เส้นตาราง/ช่องเครดิต-เกรดปนกับชื่อวิชา, หัวภาคเรียนที่เสียทำให้จัดภาคผิด และ fallback นำรหัสวิชาไปเป็นรหัสนักศึกษา
- แก้ geometry ให้หาจุดตัดขอบจริงและคงเส้นทางเดิมสำหรับภาพหมุนมาก; เพิ่ม `model/screen_table.py` ลดลายจอ/ปรับแสงแบบ grayscale ก่อนขยาย, หาเส้นคอลัมน์, อ่านเครดิต/เกรดตาม y ของแต่ละแถว, อ่านหัวภาคและเลขนักศึกษาซ้ำ. ช่องอ่านไม่ได้เก็บ null โดยรักษาแถวและชื่อที่ขึ้นบรรทัดใหม่; ภาพถ่ายจอมีคำเตือนต้องตรวจทาน. เกณฑ์เลือกเฉพาะ unofficial English และเคารพ format override
- หลังแก้ได้ 423/600 = **70.50%**; แยกภาพตาม prefix: `19b631b5` 105/150, `26e37977` 82/150, `6cca1647` 120/150, `f77ae849` 116/150. พบแถว 32,31,32,32 ตามลำดับ แต่แถวที่รหัส+ภาคถูกต้องคือ 25,16,29,22; precision 80.70%, recall 71.88%, F1 76.03%. Header 83.33%, semester 69.74%, course fields 71.72%; footer/summary ยัง 0%. ค่า GPA สะสม/ท้ายเอกสารยังเชื่อถือไม่ได้ ไม่อ้างว่าอ่านถูกทั้งหมด
- เป็น development regression ของเอกสารเดียว 4 มุม ไม่ใช่ holdout อิสระ. เวลาเฉลี่ย 30.90 วินาที (ทดสอบพร้อม regression จึงได้รับผลจากโหลดเครื่อง); API จริงภาพแรกใช้ 27.032 วินาที ได้ 32 แถวและรหัสนักศึกษาถูกต้อง ผล record ตรงกับ CLI ทุกฟิลด์
- Regression original 12 ฉบับไม่ลดคะแนนทุกฉบับ: 1,281→1,284/1,338 = 95.96%, 201 แถวถูกต้องครบ. ภาพหมุนเดิม `1.jpg` เทียบ baseline โค้ดปัจจุบันได้ 58/145 และ 27/30 แถวเท่ากัน; ไม่ใช้รายงานเดือนกันยายนคนละ code state เป็นฐานเทียบ. Unit tests 83 รายการผ่าน และ diff check ผ่าน
- ทดลอง tessdata_best/RapidOCR แล้วไม่ได้ใช้ในเส้นทางสุดท้าย; ลบ weights และ packages ทดลองที่เพิ่มมาแล้ว ไม่มี dependency ใหม่หรือการ train weights ด้วย peam. รีสตาร์ท backend เดิมที่ mount โค้ดใหม่; ยกเลิก rebuild ที่จะเปลี่ยน base image/runtime โดยไม่จำเป็น. เว็บ `http://localhost:3000/upload`, proxy health `ok`, อัปโหลดผ่าน `/api/proxy/transcripts/extract` สำเร็จ
- ระหว่าง cleanup ลบ tmp scripts ที่ tracked ติดไป 5 ไฟล์ จึงกู้คืนจาก HEAD ครบและตรวจ status แล้ว ไม่มีการเปลี่ยนไฟล์เหล่านั้นหลงเหลือ
- หลักฐาน: `model/reports/peam-angles-matrix-20261004.md`, `peam-angles-before-20261004.json`, `peam-angles-after-20261004.json`, `peam-angle-api-20261004.json`, `image-original-test-screen-regression-20261004.json`, `old-photo-baseline-20261004.json`, `old-photo-screen-regression-20261004.json`. ไม่มี commit
