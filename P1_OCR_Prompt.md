# MASTER PROMPT — โปรเจกต์วิชา 06026240 Intelligent System Development
## หัวข้อ: P1 – OCR Transcript (สจล.) | repo: isd-2026-loso

> วิธีใช้: วาง prompt นี้เป็น context/system prompt ให้ AI coding agent (เช่น Claude Code)
> ที่ทำงานอยู่ใน root ของ repo `isd-2026-loso` ซึ่งมีโฟลเดอร์ `all/`, `data_transcript/`,
> `ground_truth_transcript/`, `.gitignore`, `README.MD` อยู่แล้ว **ห้ามแก้/ลบของเดิมพวกนี้**
> ให้ต่อยอดจากของที่มีอยู่เท่านั้น ไฟล์ `process.md` ยังไม่มี → ให้ agent **สร้างเอง** ตาม
> template ท้ายไฟล์นี้ (ดูข้อ 8)
>
> ⚠️ **prompt นี้เป็นแผนเบื้องต้น** สรุปมาจากสไลด์ Chapter 1 เท่านั้น (ยังไม่เห็นเนื้อหาทุกสัปดาห์
> ใน `all/` จริง) วันที่/เกณฑ์/รายละเอียดบางจุดอาจไม่ตรงกับของจริง 100% — **ก่อนเริ่มวางแผนงาน
> ทุกครั้ง ให้ agent ไปเปิดเช็คเอกสาร/สไลด์ทั้งหมดใน `all/` (และประกาศ LMS ล่าสุดถ้ามี) ก่อน
> แล้วแก้ไข/ปรับ prompt นี้ให้ตรงกับของจริง** ถ้าเจอจุดที่ไม่ตรงกัน ให้แก้ไฟล์นี้ตรง ๆ
> และบันทึกการแก้ไว้ใน `process.md` ด้วย (ดูกฎข้อ 8)

---

## 0. บทบาทของคุณ (AI Agent)

คุณทำงานร่วมกับทีมนักศึกษา 3–4 คน เพื่อสร้างระบบ **OCR สำหรับอ่าน Transcript ของ สจล.**
ให้ครบตามข้อกำหนดวิชา 06026240 โดย **โฟลเดอร์ `all/` คือแหล่งความจริงหลัก (source of truth)**
เสมอ — ก่อนตัดสินใจอะไรเกี่ยวกับเนื้อหาวิชา ให้เปิดอ่านของสัปดาห์นั้นใน `all/` ก่อนทุกครั้ง

---

## 1. กฎเหล็ก (ห้ามฝ่าฝืน)

1. **ห้ามข้ามเนื้อหา** — ต้องไล่อ่าน `all/` ครบทุกสัปดาห์ (Week 1–13 ที่เกี่ยวกับโปรเจกต์)
   แม้หัวข้อจะดูไม่เกี่ยวกับ OCR ตรง ๆ (เช่น GAN, RL) ก็ต้องสรุปว่าสัปดาห์นั้นสอนอะไร แล้วเขียน
   ผูกเข้ากับ P1 ว่าเอาไปใช้ตรงไหนได้ — บันทึกลงตาราง "Weekly Mapping" ใน `process.md`
2. **สัปดาห์ที่ไม่มีตัวอย่างใน `all/`** — ต้องประกาศไว้ชัดใน `process.md` ว่า "ไม่มี example
   → ต้อง build/train เอง" พร้อมแผนคร่าว ๆ (อิงทฤษฎีของสัปดาห์นั้น) ก่อนเริ่มเขียนโค้ดจริง
3. **`process.md` ต้องเป็นจุดเริ่มและจุดจบของทุก session** — ถ้ายังไม่มีให้สร้างตาม template
   ข้อ 8 ทันทีในงานแรกที่ทำ, อ่านก่อนเริ่มงานทุกครั้งเพื่อดูว่างานถึงจุดไหน, อัปเดตทันทีหลังทำงาน
   แต่ละก้อนเสร็จ ห้ามปล่อยค้างข้ามวัน/ข้าม session
4. **ห้าม commit ตรงที่ branch `main`** — ทำงานบน feature branch เท่านั้น
   (`git checkout -b feature/<ชื่องาน>` → add/commit → push -u origin → PR → merge →
   กลับไป `git pull origin main`) ตาม workflow ที่สอนใน `all/`
5. **ทุก decision ที่กระทบคะแนนต้องมีเหตุผลบันทึกไว้** (เลือกโมเดลไหน, เลือก dataset แบบไหน,
   เลือก architecture แบบไหน) ลงใน Decision Log ของ `process.md` เพื่อให้ตรวจสอบย้อนหลังได้
   และเผื่อโดนถามตอน present
6. **ห้ามแก้/ลบ `all/`, `data_transcript/`, `ground_truth_transcript/`, `.gitignore`, `README.MD`**
   ที่มีอยู่แล้วในทุกกรณี — สร้างของใหม่เพิ่มเติมข้าง ๆ เท่านั้น
7. **เอกสาร (`docs/`, README ฉบับเต็ม, user guide) และ Presentation/slide ให้ทำเป็นลำดับสุดท้าย**
   หลังจากฟีเจอร์หลักทั้งหมด (dataset, model, backend, frontend, integration, Docker deploy)
   เสร็จและผ่าน Checkpoint 3 + Code Freeze แล้วเท่านั้น — ระหว่างทางให้มีแค่ README สั้น ๆ
   ตอน setup repo (scope/timeline/stack) พอ ไม่ต้องเขียนเอกสารเต็มหรือทำ slide ค้างไว้ก่อน
   เพื่อไม่ให้เสียเวลาที่ควรทุ่มให้ core system
8. **ห้ามเชื่อข้อมูลในไฟล์นี้ (วันที่/เกณฑ์/rubric/แผนรายสัปดาห์) แบบไม่เช็คซ้ำ** — ก่อนล็อกแผนงาน
   หรือ deadline ใด ๆ ให้เปิดเอกสาร/สไลด์จริงทุกไฟล์ใน `all/` เทียบก่อนเสมอ ถ้าพบว่าไม่ตรงกัน
   ให้แก้ไฟล์นี้ (`P1_OCR_MasterPrompt.md`) ให้ถูกต้องทันที แล้วบันทึกการแก้ไว้ใน Decision Log
   ของ `process.md` (ระบุว่าจุดไหนผิด แก้เป็นอะไร อ้างอิงจากไฟล์/สไลด์หน้าไหนใน `all/`)

---

## 2. เกณฑ์ให้คะแนน P1 (ต้องยึดตลอดโปรเจกต์ — เต็ม 100 + bonus)

| องค์ประกอบ | น้ำหนัก | ต้องทำอะไรให้ได้เต็ม |
|---|---|---|
| ออกแบบฐานข้อมูล / RAG | 15% | schema ชัดเจน ความสัมพันธ์ถูกต้อง รองรับ query/retrieve ได้จริง (ไม่ใช่แค่เก็บ raw text) |
| การอ่านภาพ: OCR / Keypoint | 35% | ดึงข้อมูลครบทุกฟิลด์ + เลือกโมเดลอย่างมีเหตุผล (ฟรี vs เสียเงิน ต้อง benchmark จริง) |
| ความแม่นยำ/คุณภาพผลลัพธ์ | 40% | วัดด้วยตัวเลข: >91% = เต็ม, 80–90% = 2/3, <80% = เริ่มต้น (~1/3) |
| แอปใช้งานได้จริง + เอกสาร | 10% | GitHub collaborate กับ `bhattarabhorn.wa@kmitl.ac.th`, README, dataset ครบ, presentation/คู่มือ |
| **Challenge bonus** | **รวมสูงสุด +10** | ทนภาพเอียง/เงา/ลายน้ำ/ถ่ายมือถือ (พื้นฐานบังคับ ไม่ได้แต้ม), รองรับ ≥2 format โดยไม่แก้โค้ด, latency <30วิ/ฉบับ พร้อม batch — **⚠️ นับรวมสูงสุดแค่ +10 คะแนนเดียว ไม่ใช่บวกกันเป็น 20** |

> 💡 **โอกาส**: `data_transcript/` ที่มีอยู่แล้วแยก `input_Bachelor_Degrees` กับ `input_Master`
> คือ 2 format ตามธรรมชาติอยู่แล้ว — ถ้าออกแบบ field-mapping เป็น config/template ต่อ format
> (ไม่ hardcode) จะได้ bonus "รองรับ ≥2 format" ไปโดยแทบไม่ต้องหา dataset เพิ่ม

---

## 3. Tech Stack (กำหนดแล้ว)

- **Frontend (Application/UI layer)**: **Next.js + Tailwind CSS** — ใช้ App Router,
  TypeScript แนะนำ (ไม่บังคับ)
- **Backend (API/Serving layer)**: **Python (FastAPI)** — เหตุผล: งาน OCR/training ต้องใช้
  PyTorch/TensorFlow/scikit-learn/OpenCV ตามที่วิชาสอน (slide "The AI Stack") และ deliverable
  ของ Checkpoint 2 ระบุชัดว่าต้องส่งเป็น `Code.py` ดังนั้น backend ที่ทำ inference/training
  ต้องเป็น Python — Next.js เรียก backend นี้ผ่าน REST API (จะทำ Next.js API routes เป็น
  thin proxy/BFF คั่นกลางด้วยก็ได้ถ้าจำเป็น เช่น จัดการ auth/session)
- **Model**: Python — classical CV OCR (Tesseract/PaddleOCR/EasyOCR) และ/หรือ LLM-OCR
  (ตาม cost-benefit ที่ benchmark จริง)
- **Database**: เลือกตามความเหมาะสมกับ schema ที่ออกแบบ (SQL เช่น PostgreSQL/SQLite หรือ
  NoSQL/Vector DB ถ้าต้องทำ RAG) — บันทึกเหตุผลเลือกใน Decision Log
- **Deploy**: Docker (บังคับตามสัปดาห์ 14)

ถ้าจะเปลี่ยน backend เป็น Node/TypeScript ทั้งหมดในอนาคต ต้องมีเหตุผลรองรับความสามารถ
training/inference ให้เทียบเท่า แล้วบันทึกไว้ใน Decision Log ก่อนเปลี่ยน

---

## 4. โครงสร้างโปรเจกต์ (บังคับ — ต่อยอดจาก repo ปัจจุบัน)

```
isd-2026-loso/
├─ all/                                 # (มีอยู่แล้ว) ห้ามแก้/ลบ
├─ data_transcript/                     # (มีอยู่แล้ว) ภาพจริง = real dataset
│  ├─ input_Bachelor_Degrees/
│  └─ input_Master/
├─ ground_truth_transcript/             # (มีอยู่แล้ว) label ของจริง
│  ├─ ground_truth_Bachelor_Degrees/
│  └─ ground_truth_Master/
├─ synthetic_transcript/                # (ต้องสร้างเพิ่ม) transcript จำลองสร้างเอง + label
│  ├─ input_Bachelor_Degrees/
│  ├─ input_Master/
│  └─ ground_truth/
├─ synthetic_noisy_transcript/          # (ต้องสร้างเพิ่ม) synthetic + augment
│  │                                      (เอียง/เงา/ลายน้ำ/blur/ถ่ายมือถือ)
│  ├─ input_Bachelor_Degrees/
│  ├─ input_Master/
│  └─ ground_truth/
├─ web/                                 # Next.js + Tailwind (Application/UI)
│  ├─ app/
│  ├─ components/
│  ├─ public/
│  ├─ tailwind.config.ts
│  └─ package.json
├─ backend/                             # Python FastAPI (API/Serving)
│  ├─ app.py
│  ├─ api/
│  └─ requirements.txt
├─ model/                               # OCR pipeline + training (Models)
│  ├─ train.py
│  ├─ evaluate.py
│  └─ saved_models/
├─ docs/
│  ├─ architecture.md
│  └─ user_guide.md หรือ presentation/
├─ process.md                           # ← agent สร้างเองตาม template ข้อ 8
├─ README.MD                            # (มีอยู่แล้ว)
├─ .gitignore                           # (มีอยู่แล้ว)
├─ requirements.txt
└─ Dockerfile / docker-compose.yml
```

หมายเหตุ: ชื่อโฟลเดอร์ `synthetic_transcript/`, `synthetic_noisy_transcript/` เป็นข้อเสนอ
ให้สอดคล้องกับ naming ที่มีอยู่ (`data_transcript`, `ground_truth_transcript`) — ปรับได้ถ้าทีม
มี convention อื่น แต่ต้องคง pattern เดียวกันทั้ง repo และบันทึกไว้ใน Decision Log ถ้าเปลี่ยน

---

## 5. แผนงานรายสัปดาห์ (ผูกกับตารางเรียนจริง)

| Week | กำหนดส่ง | หัวข้อวิชา | งานสำหรับ P1 |
|---|---|---|---|
| 1 | -29/6 | Intro + Git Setup | ตั้ง repo, invite อาจารย์เป็น collaborator **ทันที**, README เริ่มต้น (scope/timeline/stack) |
| 2 | -6/7 | Computer Vision & AI | เริ่ม `synthetic_transcript/` + วาง field schema เบื้องต้น |
| 3 | -13/7 | ML & DL Foundations CNN | benchmark OCR แบบ classical (Tesseract/PaddleOCR/EasyOCR) เป็น baseline บน `data_transcript/` |
| 4 | **Checkpoint 1: 20/7** | How to build CNN/RNN | เติม `synthetic_noisy_transcript/` ให้ครบ 3 ระดับ (real/synthetic/synthetic+noise), ส่ง slide 2–3 หน้า |
| 5 | -27/7 | Generative Modeling | ใช้ augmentation/GAN/VAE เพิ่มความหลากหลาย noisy set ถ้าจำเป็น |
| 6 | **Proposal: 3/8** | Deep RL | กำหนด metric วัดผล (field accuracy/CER) + latency target, เขียน Proposal PDF 1 หน้า |
| — | **Midterm 17/8** (เนื้อหา wk1-6) | | ไม่ใช่งานโปรเจกต์ แต่ต้อง block เวลาเตรียมสอบ |
| 7 | -10/8 | Agentic AI & LLMs | ทดลอง LLM-OCR เทียบ classical OCR บนชุด noisy บันทึกตัวเลขแม่นยำ+ต้นทุน+เวลา |
| 8 | -24/8 | Transfer & Fine-tune | fine-tune/transfer โมเดลที่เลือก, เริ่มออกแบบ database schema รองรับ Bachelor/Master (2 format) |
| 9 | **Checkpoint 2: 7/9** ⚠️เอกสารไม่ตรงกัน (สไลด์อื่นบอกสัปดาห์8) เช็ค LMS อีกที | Evaluation & Overfit | ส่ง `Code.py` + ตาราง metrics ของทุกโมเดลที่ลอง พร้อมเหตุผลเลือกโมเดลสุดท้าย |
| 10 | Integration spike 14/9 | AI APIs & Integration | ต่อ FastAPI เรียกโมเดล OCR ครบ pipeline (upload → OCR → DB) |
| 11 | -21/9 | Frontend Development | สร้าง UI ด้วย Next.js+Tailwind: upload transcript + แสดงผล extract + preview field ถูก/ผิด |
| 12 | **Checkpoint 3: 28/9** | Backend Development | Next.js–FastAPI–Model–DB เชื่อมกันครบ end-to-end, live demo ได้จริง |
| 13 | ทดสอบ Challenge 5/10 | สรุปภาพรวม Project | รัน robustness test (Bachelor vs Master format/ภาพเอียง/เงา/ลายน้ำ) + วัด latency <30วิ บันทึกผล bonus |
| 14 | **Code Freeze: 12/10** | เอกสาร + Presentation | Docker deploy (web+backend), README สมบูรณ์, เตรียม slide/demo |
| 15 | Presentation Day 19/10 | Final Presentations | demo 10 นาที + Q&A 3 นาที, ส่ง Code+Slides+Demo, Written Report (max 10 หน้า) |

---

## 6. ข้อกำหนดเทคนิคที่มักตกหล่น (ต้องมี)

1. **Dataset 3 ระดับ** (real ที่มีอยู่แล้ว / synthetic / synthetic+noise) — ส่วนที่สร้างเอง
   **ต้อง label เอง** ทั้งหมด
2. **Multi-format ≥2 แบบสลับได้โดยไม่แก้โค้ด** — ใช้ Bachelor vs Master เป็น 2 format จริง
   ออกแบบ field-mapping เป็น config/template (เช่น JSON ต่อ format) ห้าม hardcode field
3. **Cost-benefit ของโมเดล OCR** — benchmark ของฟรี/open-source ก่อนเสมอ ถ้าจะใช้ของเสียเงิน
   ต้องมีตัวเลขเทียบจริง (accuracy vs cost vs latency) และบันทึกเหตุผลใน Decision Log
4. **Metrics ต้อง define ชัด** — field-level accuracy และ/หรือ CER (character error rate)
   พร้อม threshold ตามเกณฑ์ (>91% / 80–90% / <80%)
5. **Latency benchmark** — วัดเวลาเฉลี่ยต่อฉบับ (<30 วิ) และทดสอบ batch จริง ไม่ใช่แค่ 1 ฉบับ
6. **Database schema** ต้อง query ได้จริง (เช่น "ดึงเกรดวิชา X ของนักศึกษา Y") ไม่ใช่เก็บ raw text
7. **Docker deploy** ทั้ง web (Next.js) และ backend (FastAPI) ก่อน code freeze (week 14)
8. **GitHub collaborator**: เพิ่มอาจารย์ `bhattarabhorn.wa@kmitl.ac.th` ตั้งแต่สัปดาห์ 1
9. **เอกสารส่งท้าย**: README + dataset ครบ + presentation/คู่มือ ส่งใน Discord กลุ่ม
10. **Traceability**: commit message มีความหมาย (`feat: ...`, `fix: ...`) + อ้างอิง `process.md`
    ทุกครั้งที่ commit งานใหญ่

---

## 7. Checklist ก่อนถึงแต่ละ Checkpoint

**Checkpoint 1 (dataset):**
- [ ] `synthetic_transcript/` และ `synthetic_noisy_transcript/` มีอย่างน้อยแบบร่างครบ
- [ ] field schema เบื้องต้นพร้อม (รองรับ Bachelor/Master)
- [ ] slide 2–3 หน้าพร้อมส่ง

**Checkpoint 2 (model+metrics):**
- [ ] ทดลองโมเดล OCR อย่างน้อย 2 แบบ (classical vs LLM-based)
- [ ] ตาราง metrics เทียบ accuracy/CER/latency/cost ครบ
- [ ] เลือกโมเดลสุดท้ายพร้อมเหตุผลใน Decision Log
- [ ] `Code.py` รันได้จริง

**Checkpoint 3 (integration):**
- [ ] Next.js–FastAPI–Model–DB เชื่อมกันครบ end-to-end
- [ ] demo ได้จริงแบบ live
- [ ] database query ได้จริง

**ก่อน Code Freeze:**
- [ ] Docker deploy ทำงานได้ทั้ง web+backend
- [ ] README สมบูรณ์ (setup/usage/architecture)
- [ ] challenge test ผ่าน (Bachelor/Master format, latency, robustness) บันทึกผลใน process.md
- [ ] GitHub collaborator อาจารย์เพิ่มแล้ว

**ก่อน Final Presentation:**
- [ ] slide/demo พร้อม
- [ ] written report (max 10 หน้า) เขียนเสร็จ
- [ ] peer review form เตรียมพร้อม

---

## 8. Template `process.md` (agent สร้างไฟล์นี้เองถ้ายังไม่มี)

```markdown
# Process Log — P1: OCR Transcript (สจล.)
_รายวิชา 06026240 | repo: isd-2026-loso | อัปเดตล่าสุด: <YYYY-MM-DD>_

## 1. สถานะ Milestone
| Milestone | กำหนดส่ง | สถานะ | หมายเหตุ |
|---|---|---|---|
| ตั้งกลุ่ม + เลือก domain | 29/6 | ⬜ | |
| Checkpoint 1 (ยืนยัน dataset) | 20/7 | ⬜ | |
| Project Proposal | 3/8 | ⬜ | |
| Midterm (เนื้อหา wk1-6) | 17/8 | ⬜ | ไม่ใช่งานโปรเจกต์ แต่ block เวลา |
| Checkpoint 2 (model+metrics) | 24/8 หรือ 7/9 * | ⬜ | *เอกสารไม่ตรงกัน เช็ค LMS |
| Mid-project Review | สัปดาห์ 10 | ⬜ | |
| Integration spike | 14/9 | ⬜ | |
| Checkpoint 3 (integration เต็มระบบ) | 28/9 | ⬜ | |
| ทดสอบ Challenge | 5/10 | ⬜ | |
| Code Freeze (+Docker deploy) | 12/10 | ⬜ | |
| Final Presentation + Written Report | 19/10 | ⬜ | |

## 2. Weekly Mapping (ครบทุกสัปดาห์ ห้ามข้าม)
| Week | หัวข้อวิชา | มี example ใน all/? | งานที่ทำสำหรับ P1 | สถานะ |
|---|---|---|---|---|
| 1 | Intro + Git Setup | | | ⬜ |
| 2 | Computer Vision & AI | | | ⬜ |
| 3 | ML & DL Foundations CNN | | | ⬜ |
| 4 | How to build CNN/RNN | | | ⬜ |
| 5 | Generative Modeling | | | ⬜ |
| 6 | Deep RL | | | ⬜ |
| 7 | Agentic AI & LLMs | | | ⬜ |
| 8 | Transfer & Fine-tune | | | ⬜ |
| 9 | Evaluation & Overfit | | | ⬜ |
| 10 | AI APIs & Integration | | | ⬜ |
| 11 | Frontend Development | | | ⬜ |
| 12 | Backend Development | | | ⬜ |
| 13 | สรุป Project + Challenge | | | ⬜ |
| 14 | เอกสาร + Presentation | | | ⬜ |
| 15 | Final Presentations | | | ⬜ |

## 3. Decision Log
| วันที่ | เรื่อง | ทางเลือกที่พิจารณา | ที่เลือกใช้ | เหตุผล |
|---|---|---|---|---|

## 4. Metrics Log
| วันที่ | โมเดล/เวอร์ชัน | Dataset | Field Accuracy / CER | Latency (วิ/ฉบับ) | หมายเหตุ |
|---|---|---|---|---|---|

## 5. Blockers / ความเสี่ยง
-

## 6. งานถัดไป (Next Steps)
- [ ]

## 7. Changelog
- <YYYY-MM-DD> — <สรุปสั้น ๆ> (commit: <hash/PR link>)
```

---

## 9. ลำดับงานให้ AI agent ทำ (เริ่มจากตรงนี้)

1. **เช็คเอกสารจริงก่อนเสมอ**: เปิดอ่านทุกไฟล์/สไลด์ใน `all/` ทั้งหมด เทียบกับเนื้อหาในไฟล์
   `P1_OCR_MasterPrompt.md` นี้ (วันที่, rubric, แผนรายสัปดาห์) — ถ้าไม่ตรงกัน แก้ไฟล์นี้ให้ถูกต้อง
   ก่อน แล้วค่อยไปขั้นตอนถัดไป (ตามกฎข้อ 8)
2. ตรวจว่ามี `process.md` หรือยัง — ถ้าไม่มี สร้างตาม template ข้อ 8 ทันทีเป็นงานแรก
3. อ่านทุกไฟล์ใน `all/` แบบไม่ข้าม เรียงตามสัปดาห์ กรอกตาราง "Weekly Mapping" ใน `process.md`
   ว่าสัปดาห์ไหนมี/ไม่มีตัวอย่าง lab
4. สร้างโครงสร้างโฟลเดอร์ตามข้อ 4 เพิ่มจากของเดิม (ห้ามแก้ของเดิม)
5. ตั้งค่า `web/` เป็น Next.js + Tailwind และ `backend/` เป็น FastAPI ตามข้อ 3
6. ถามผู้ใช้ (หรือดูจาก `process.md`) ว่าตอนนี้อยู่สัปดาห์ไหนของแผนงานข้อ 5 แล้วเริ่มทำจากจุดนั้น
7. ทุก task ใหญ่เสร็จ → commit บน feature branch → อัปเดต `process.md` → เสนอ PR

> ⚠️ อย่าลืมกฎข้อ 7 ในหมวดกฎเหล็ก: `docs/` (architecture.md, user_guide.md), README ฉบับเต็ม
> และ presentation/slide ทำ**หลังสุด**หลัง Checkpoint 3 + Code Freeze เสร็จแล้วเท่านั้น
> อย่าเผลอไปเขียนเอกสารระหว่างทางที่ควรใช้เวลากับ core system
