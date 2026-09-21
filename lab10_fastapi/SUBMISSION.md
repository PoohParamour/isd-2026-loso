# Lab 10 submission

โฟลเดอร์นี้รวมไฟล์ที่จำเป็นสำหรับ Transcript FastAPI แล้ว:

```text
lab10_fastapi/
├── __init__.py
├── README.md
├── SUBMISSION.md
├── src/ocr_system/
│   ├── __init__.py
│   ├── lab7_metrics.py
│   ├── lab7a_transcript.py
│   └── lab8a_denoise.py
└── transcript_app/
    ├── __init__.py
    ├── .env.example
    ├── config.py
    ├── main.py
    ├── pipeline_service.py
    ├── schemas.py
    ├── requirements.txt
    ├── README.md
    └── static/index.html
```

ไม่ต้องส่ง `.venv`, `__pycache__`, `.env` หรือ `.pytest_cache`

## วิธีรันหลังแตกไฟล์

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r lab10_fastapi/transcript_app/requirements.txt
python -m uvicorn lab10_fastapi.transcript_app.main:app --reload --port 8001
```

เปิดหน้าเว็บที่ <http://127.0.0.1:8001/> และ Swagger ที่
<http://127.0.0.1:8001/docs>
