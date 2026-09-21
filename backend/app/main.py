"""Transcript upload, extraction, review, persistence, and grade lookup API."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from model.extract import FORMATS, extract
from .database import get_document, init_db, save_document, search_grades


MAX_UPLOAD = 20 * 1024 * 1024
ALLOWED = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".heic", ".heif"}
HEIF_BRANDS = {b"heic", b"heix", b"hevc", b"hevx", b"heim", b"heis", b"mif1", b"msf1"}


def is_heif(content: bytes) -> bool:
    """Check the ISO-BMFF file-type box used by HEIC/HEIF images."""
    if len(content) < 16 or content[4:8] != b"ftyp":
        return False
    box_size = int.from_bytes(content[:4], "big")
    if box_size < 16 or box_size > len(content):
        return False
    brands = {content[offset : offset + 4] for offset in range(8, box_size, 4)}
    return bool(brands & HEIF_BRANDS)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="KMITL Transcript OCR", version="0.1.0", lifespan=lifespan)
origins = os.getenv("OCR_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=False, allow_methods=["GET", "POST"], allow_headers=["*"])


class SaveRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    record: dict[str, Any]
    engine: str | None = None
    processing_seconds: float | None = None


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "tesseract": shutil.which("tesseract") is not None, "pdftotext": shutil.which("pdftotext") is not None, "formats": sorted(FORMATS)}


@app.post("/api/transcripts/extract")
async def extract_transcript(file: UploadFile = File(...), format_id: str | None = Form(default=None), force_ocr: bool = Form(default=False)) -> dict:
    filename = Path(file.filename or "upload").name
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED:
        raise HTTPException(415, "รองรับ PDF, PNG, JPG, TIFF และ HEIC/HEIF")
    if format_id and format_id not in FORMATS:
        raise HTTPException(422, "ไม่รู้จักรูปแบบ transcript")
    content = await file.read(MAX_UPLOAD + 1)
    if len(content) > MAX_UPLOAD:
        raise HTTPException(413, "ไฟล์ใหญ่เกิน 20 MB")
    if suffix == ".pdf" and not content.startswith(b"%PDF"):
        raise HTTPException(415, "ไฟล์ PDF ไม่ถูกต้อง")
    if suffix == ".png" and not content.startswith(b"\x89PNG\r\n\x1a\n"):
        raise HTTPException(415, "ไฟล์ PNG ไม่ถูกต้อง")
    if suffix in {".jpg", ".jpeg"} and not content.startswith(b"\xff\xd8"):
        raise HTTPException(415, "ไฟล์ JPEG ไม่ถูกต้อง")
    if suffix in {".heic", ".heif"} and not is_heif(content):
        raise HTTPException(415, "ไฟล์ HEIC/HEIF ไม่ถูกต้อง")
    try:
        with tempfile.TemporaryDirectory(prefix="isd_upload_") as temp:
            path = Path(temp) / f"input{suffix}"
            path.write_bytes(content)
            result = await run_in_threadpool(extract, path, format_id, force_ocr)
            return {"filename": filename, **result}
    except subprocess.CalledProcessError as exc:
        raise HTTPException(422, "อ่านไฟล์นี้ไม่สำเร็จ กรุณาตรวจไฟล์ต้นฉบับ") from exc
    except (ValueError, RuntimeError, OSError) as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/api/documents")
def save_transcript(payload: SaveRequest) -> dict:
    try:
        document_id = save_document(payload.record, payload.filename, payload.engine, payload.processing_seconds)
        return {"document_id": document_id}
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/api/documents/{document_id}")
def document(document_id: str) -> dict:
    result = get_document(document_id)
    if result is None:
        raise HTTPException(404, "ไม่พบเอกสาร")
    return result


@app.get("/api/grades")
def grades(student_id: str | None = None, subject_id: str | None = None) -> dict:
    try:
        rows = search_grades(student_id, subject_id)
        return {"count": len(rows), "results": rows}
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
