"""Deterministic validation for extracted transcript records."""

from __future__ import annotations

import re
from typing import Any


VALID_GRADES = {"a", "b+", "b", "c+", "c", "d+", "d", "f", "w", "s", "u", "i", "p", "np", "g", "-"}


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def validate_record(record: dict[str, Any]) -> dict[str, Any]:
    """Return machine-readable issues and a conservative review decision."""
    issues: list[dict[str, str]] = []

    def add(path: str, code: str, message: str, severity: str = "warning") -> None:
        issues.append({"path": path, "code": code, "message": message, "severity": severity})

    header = record.get("header_detail") or {}
    student_id = str(header.get("student_id") or "")
    if not re.fullmatch(r"\d{8}", student_id):
        add("header_detail.student_id", "invalid_student_id", "รหัสนักศึกษาต้องเป็นตัวเลข 8 หลัก", "error")
    for field, label in (("name", "ชื่อ-สกุล"), ("faculty_name", "คณะ"), ("program", "หลักสูตร")):
        if not str(header.get(field) or "").strip():
            add(f"header_detail.{field}", "missing_field", f"ไม่พบ{label}")

    detail = record.get("transcript_detail") or {}
    semesters = detail.get("semesters") or []
    if not semesters:
        add("transcript_detail.semesters", "missing_semesters", "ไม่พบภาคการศึกษา", "error")
    course_count = 0
    for sem_index, semester in enumerate(semesters):
        prefix = f"transcript_detail.semesters[{sem_index}]"
        year = semester.get("year")
        if year is not None and (not isinstance(year, int) or not 2400 <= year <= 2700):
            add(f"{prefix}.year", "invalid_year", "ปีการศึกษาอยู่นอกช่วงที่รองรับ")
        number = semester.get("sem_num")
        if number not in {0, 1, 2, 3}:
            add(f"{prefix}.sem_num", "invalid_semester", "ภาคการศึกษาต้องเป็น 0-3")
        for gpa_field in ("GPA", "GPS"):
            value = semester.get(gpa_field)
            numeric = _number(value)
            if value not in {None, ""} and (numeric is None or not 0 <= numeric <= 4):
                add(f"{prefix}.{gpa_field}", "invalid_gpa", f"{gpa_field} ต้องอยู่ระหว่าง 0.00-4.00")
        for row_index, subject in enumerate(semester.get("subject") or []):
            course_count += 1
            row = f"{prefix}.subject[{row_index}]"
            if not re.fullmatch(r"\d{8}", str(subject.get("subject_id") or "")):
                add(f"{row}.subject_id", "invalid_subject_id", "รหัสวิชาต้องเป็นตัวเลข 8 หลัก", "error")
            credit = subject.get("credit")
            if not isinstance(credit, int) or not 0 <= credit <= 30:
                add(f"{row}.credit", "invalid_credit", "หน่วยกิตต้องเป็นจำนวนเต็ม 0-30", "error")
            raw_grade = subject.get("grade_earn")
            if raw_grade in {None, ""}:
                # A current/in-progress semester legitimately has no grade.
                # Preserve the row and the null rather than treating it as a
                # malformed recognized grade.
                continue
            grade = str(raw_grade).lower()
            if grade.startswith("t(") and grade.endswith(")"):
                grade = grade[2:-1]
            if grade not in VALID_GRADES:
                add(f"{row}.grade_earn", "invalid_grade", "เกรดไม่อยู่ในรายการที่รองรับ", "error")
    if course_count == 0:
        add("transcript_detail.semesters", "missing_courses", "ไม่พบรายวิชา", "error")

    cumulative = detail.get("cumulative_gpa")
    numeric = _number(cumulative)
    if cumulative not in {None, ""} and (numeric is None or not 0 <= numeric <= 4):
        add("transcript_detail.cumulative_gpa", "invalid_gpa", "GPA สะสมต้องอยู่ระหว่าง 0.00-4.00")

    errors = sum(issue["severity"] == "error" for issue in issues)
    warnings = len(issues) - errors
    return {
        "needs_review": bool(issues),
        "errors": errors,
        "warnings": warnings,
        "course_count": course_count,
        "issues": issues,
    }
