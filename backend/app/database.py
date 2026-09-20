"""SQLite persistence for verified transcript records."""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path


DB_PATH = Path(os.getenv("OCR_DB_PATH", Path(__file__).resolve().parents[1] / "transcripts.db"))


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS students (
                student_id TEXT PRIMARY KEY,
                prename TEXT,
                name TEXT,
                degree TEXT,
                faculty_name TEXT,
                program TEXT
            );
            CREATE TABLE IF NOT EXISTS documents (
                document_id TEXT PRIMARY KEY,
                student_id TEXT NOT NULL REFERENCES students(student_id),
                filename TEXT NOT NULL,
                format_id TEXT,
                engine TEXT,
                processing_seconds REAL,
                created_at TEXT NOT NULL,
                record_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS semesters (
                semester_id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id TEXT NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
                semester_index INTEGER NOT NULL,
                academic_year TEXT,
                semester_number TEXT,
                gpa TEXT,
                gps TEXT,
                pass_reason TEXT
            );
            CREATE TABLE IF NOT EXISTS course_results (
                result_id INTEGER PRIMARY KEY AUTOINCREMENT,
                semester_id INTEGER NOT NULL REFERENCES semesters(semester_id) ON DELETE CASCADE,
                row_index INTEGER NOT NULL,
                subject_id TEXT,
                subject_name TEXT,
                subject_type TEXT,
                credit TEXT,
                grade TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_course_subject ON course_results(subject_id);
            CREATE INDEX IF NOT EXISTS idx_documents_student ON documents(student_id);
        """)


def save_document(record: dict, filename: str, engine: str | None, seconds: float | None) -> str:
    header = record.get("header_detail") or {}
    student_id = str(header.get("student_id") or "")
    if not (student_id.isdigit() and len(student_id) == 8):
        raise ValueError("กรุณาตรวจและแก้รหัสนักศึกษา 8 หลักก่อนบันทึก")
    transcript = record.get("transcript_detail") or {}
    semesters = transcript.get("semesters") or []
    if not isinstance(semesters, list):
        raise ValueError("ข้อมูลภาคการศึกษาต้องเป็นรายการ")
    document_id = str(uuid.uuid4())
    created = datetime.now(timezone.utc).isoformat()
    with connect() as conn:
        conn.execute("""
            INSERT INTO students(student_id, prename, name, degree, faculty_name, program)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(student_id) DO UPDATE SET
                prename=excluded.prename, name=excluded.name, degree=excluded.degree,
                faculty_name=excluded.faculty_name, program=excluded.program
        """, (student_id, header.get("prename"), header.get("name"), header.get("degree"), header.get("faculty_name"), header.get("program")))
        conn.execute("""
            INSERT INTO documents(document_id, student_id, filename, format_id, engine,
                                  processing_seconds, created_at, record_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (document_id, student_id, filename, record.get("format_id"), engine, seconds, created, json.dumps(record, ensure_ascii=False)))
        for si, semester in enumerate(semesters):
            cursor = conn.execute("""
                INSERT INTO semesters(document_id, semester_index, academic_year,
                                      semester_number, gpa, gps, pass_reason)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (document_id, si, str(semester.get("year") or ""), str(semester.get("sem_num") if semester.get("sem_num") is not None else ""), semester.get("GPA"), semester.get("GPS"), semester.get("pass_reason")))
            semester_id = cursor.lastrowid
            for ci, subject in enumerate(semester.get("subject") or []):
                conn.execute("""
                    INSERT INTO course_results(semester_id, row_index, subject_id,
                                               subject_name, subject_type, credit, grade)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (semester_id, ci, subject.get("subject_id"), subject.get("subject_name"), subject.get("type"), str(subject.get("credit") if subject.get("credit") is not None else ""), subject.get("grade_earn")))
    return document_id


def get_document(document_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM documents WHERE document_id = ?", (document_id,)).fetchone()
    if row is None:
        return None
    result = dict(row)
    result["record"] = json.loads(result.pop("record_json"))
    return result


def search_grades(student_id: str | None, subject_id: str | None) -> list[dict]:
    if not student_id and not subject_id:
        raise ValueError("ระบุรหัสนักศึกษาหรือรหัสวิชาอย่างน้อยหนึ่งช่อง")
    conditions, params = [], []
    if student_id:
        conditions.append("d.student_id = ?")
        params.append(student_id)
    if subject_id:
        conditions.append("c.subject_id = ?")
        params.append(subject_id)
    sql = """
        SELECT d.document_id, d.student_id, s.prename, s.name,
               t.academic_year, t.semester_number,
               c.subject_id, c.subject_name, c.credit, c.grade
        FROM course_results c
        JOIN semesters t ON t.semester_id = c.semester_id
        JOIN documents d ON d.document_id = t.document_id
        JOIN students s ON s.student_id = d.student_id
        WHERE """ + " AND ".join(conditions) + " ORDER BY d.created_at DESC, t.semester_index, c.row_index LIMIT 200"
    with connect() as conn:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]
