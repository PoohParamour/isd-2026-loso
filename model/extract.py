"""Fast transcript extraction for digital PDFs and scanned images.

This is a deterministic baseline. It does not read ground-truth labels or file
names during inference. PDF text is used only when the embedded text is usable;
otherwise pages are rendered and read by Tesseract.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

try:
    from model.validate import validate_record
    from model.course_catalog import apply_course_catalog
except ModuleNotFoundError:  # Direct execution: python model/extract.py
    from validate import validate_record
    from course_catalog import apply_course_catalog

ROOT = Path(__file__).resolve().parents[1]
FORMATS = json.loads((Path(__file__).parent / "formats.json").read_text(encoding="utf-8"))
TH_MONTHS = {"มกราคม": 1, "กุมภาพันธ์": 2, "มีนาคม": 3, "เมษายน": 4, "พฤษภาคม": 5, "มิถุนายน": 6, "กรกฎาคม": 7, "สิงหาคม": 8, "กันยายน": 9, "ตุลาคม": 10, "พฤศจิกายน": 11, "ธันวาคม": 12}
EN_MONTHS = {"january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6, "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12}
COURSE = re.compile(r"^\s*(\d{8})[.\s]+(.+?)\s+(?:(Cr|Nc|Ad)\s+)?(\d{1,2})\s+([A-F][+]?|S|I|W|P|NP|U|G|T\([A-FS][+]?\)|-)\s*$", re.I)
COURSE_NO_GRADE = re.compile(r"^\s*(\d{8})[.\s]+(.+?)\s+(Cr|Nc|Ad)\s+(\d{1,2})\s*$", re.I)
TH_TERM = re.compile(r"ภาคการศึกษา(?:ที่|ที)\s*([123])\s*ปีการศึกษา\s*(\d{4})")
EN_TERM = re.compile(r"\b([123])(?:st|nd|rd|th)\s+Semester[,]?(?:\s+Academic\s+Year)?\s*(\d{4})", re.I)
TH_SPECIAL = re.compile(r"ภาคการศึกษาพิเศษ\s*ปีการศึกษา\s*(\d{4})")
EN_SPECIAL = re.compile(r"(?:Summer|Special)\s+Semester[,]?(?:\s+Academic\s+Year)?\s*(\d{4})", re.I)


def parse_term(line: str, language: str) -> tuple[int, int] | None:
    """Parse common semester headings without depending on one template."""
    patterns = (
        (
            r"(?:ภาคการศึกษา|ภาคเรียน)(?:ที่|ที)?\s*([123])\D{0,30}(?:ปีการศึกษา|ปี)\s*(\d{4})",
            r"(?:ปีการศึกษา|ปี)\s*(\d{4})\D{0,30}(?:ภาคการศึกษา|ภาคเรียน)(?:ที่|ที)?\s*([123])",
        )
        if language == "th"
        else (
            r"\b([123])(?:st|nd|rd|th)?\s+Semester[,]?(?:\s+Academic\s+Year)?\s*(\d{4})",
            r"\bSemester\s*([123])\D{0,30}(?:Academic\s+Year|Year)\s*(\d{4})",
            r"\b(?:Academic\s+Year|Year)\s*(\d{4})\D{0,30}Semester\s*([123])",
        )
    )
    for index, pattern in enumerate(patterns):
        match = re.search(pattern, line, re.I)
        if not match:
            continue
        if index == 1 and language == "th" or index == 2 and language == "en":
            year, semester = int(match[1]), int(match[2])
        else:
            semester, year = int(match[1]), int(match[2])
        if language == "en" and year < 2400:
            year += 543
        return semester, year
    return None


def run(*args: str, cwd: Path | None = None) -> str:
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=True)
    return result.stdout


def text_is_usable(text: str) -> bool:
    if len(text.strip()) < 300:
        return False
    damaged = sum(char == "ÿ" or (ord(char) < 32 and char not in "\t\n\r\f") for char in text)
    if damaged / len(text) > 0.02:
        return False
    return bool(re.search(r"TRANSCRIPT OF RECORDS|ใบแสดงผลการศึกษา", text, re.I))


def read_document(path: Path, force_ocr: bool = False) -> tuple[str, str]:
    if path.suffix.lower() == ".pdf" and not force_ocr:
        embedded = run("pdftotext", "-layout", str(path), "-")
        if text_is_usable(embedded):
            return embedded, "pdf_text"
    with tempfile.TemporaryDirectory(prefix="isd_ocr_") as temp:
        work = Path(temp)
        if path.suffix.lower() == ".pdf":
            subprocess.run(["pdftoppm", "-r", "250", "-png", str(path), str(work / "page")], check=True, capture_output=True)
            images = sorted(work.glob("page-*.png"))
        else:
            target = work / f"page-1{path.suffix.lower()}"
            with Image.open(path) as source:
                image = source.convert("RGB")
                if image.width * image.height > 30_000_000:
                    raise ValueError("ภาพมีขนาดพิกเซลเกิน 30 ล้านพิกเซล")
                if image.width < 2000:
                    image = image.resize((image.width * 2, image.height * 2), Image.Resampling.LANCZOS)
                image.save(target)
            images = [target]
        # English-only OCR reads the Latin grade glyphs more consistently.
        # Fall back to bilingual OCR when the English transcript marker is
        # absent, which also covers Thai image uploads.
        pages = [run("tesseract", image.name, "stdout", "-l", "eng", "--psm", "6", cwd=work) for image in images]
        combined = "\n".join(pages)
        if not re.search(r"TRANSCRIPT OF RECORDS", combined, re.I):
            pages = [run("tesseract", image.name, "stdout", "-l", "tha+eng", "--psm", "6", cwd=work) for image in images]
            combined = "\n".join(pages)
        return combined, "tesseract"


def read_bachelor_columns(path: Path, engine: str, language: str) -> str:
    """Read the left column to completion before the right column."""
    if path.suffix.lower() != ".pdf":
        with tempfile.TemporaryDirectory(prefix="isd_ocr_columns_") as temp:
            work = Path(temp)
            lang = "eng" if language == "en" else "tha+eng"
            chunks = []
            with Image.open(path) as source:
                image = source.convert("RGB")
                width, height = image.size
                if width * height > 30_000_000:
                    raise ValueError("ภาพมีขนาดพิกเซลเกิน 30 ล้านพิกเซล")
                top, bottom = round(height * 0.185), round(height * 0.93)
                middle = width // 2
                for side, box in (("left", (0, top, middle, bottom)), ("right", (middle, top, width, bottom))):
                    crop = image.crop(box)
                    if width < 2000:
                        crop = crop.resize((crop.width * 2, crop.height * 2), Image.Resampling.LANCZOS)
                    crop.save(work / f"{side}.png")
                    chunks.append(run("tesseract", f"{side}.png", "stdout", "-l", lang, "--psm", "6", cwd=work))
            return "\n".join(chunks)
    if engine == "pdf_text":
        left = run("pdftotext", "-layout", "-x", "0", "-y", "155", "-W", "297", "-H", "620", str(path), "-")
        right = run("pdftotext", "-layout", "-x", "297", "-y", "155", "-W", "298", "-H", "620", str(path), "-")
        return left + "\n" + right
    with tempfile.TemporaryDirectory(prefix="isd_ocr_columns_") as temp:
        work = Path(temp)
        lang = "eng" if language == "en" else "tha+eng"
        chunks = []
        for side, x in (("left", 0), ("right", 1033)):
            prefix = work / side
            subprocess.run(["pdftoppm", "-f", "1", "-singlefile", "-r", "250", "-x", str(x), "-y", "500", "-W", "1033", "-H", "2200", "-png", str(path), str(prefix)], check=True, capture_output=True)
            chunks.append(run("tesseract", f"{side}.png", "stdout", "-l", lang, "--psm", "6", cwd=work))
        return "\n".join(chunks)


def preprocess_image(image: Image.Image, mode: str, scale: int = 2) -> Image.Image:
    """Apply the dev-selected preprocessing without modifying source files."""
    image = image.convert("RGB")
    image = image.resize((image.width * scale, image.height * scale), Image.Resampling.LANCZOS)
    if mode == "original":
        return image
    gray = ImageOps.grayscale(image)
    if mode == "autocontrast":
        return ImageOps.autocontrast(gray, cutoff=1)
    if mode == "sharpen":
        gray = ImageEnhance.Contrast(gray).enhance(1.5)
        return gray.filter(ImageFilter.UnsharpMask(radius=2, percent=180, threshold=3))
    raise ValueError(f"Unknown preprocessing mode: {mode}")


def read_image_profile(path: Path, format_id: str) -> tuple[str, str | None]:
    """Re-read a raster image with the configuration selected on dev data."""
    profile = {
        "bachelor_th": ("original", 4),
        "bachelor_en": ("sharpen", 6),
        "graduate_th": ("sharpen", 4),
        "graduate_en": ("autocontrast", 4),
    }[format_id]
    mode, psm = profile
    language = "eng" if format_id.endswith("_en") else "tha+eng"
    with Image.open(path) as source, tempfile.TemporaryDirectory(prefix="isd_ocr_profile_") as temp:
        if source.width * source.height > 30_000_000:
            raise ValueError("ภาพมีขนาดพิกเซลเกิน 30 ล้านพิกเซล")
        work = Path(temp)

        def ocr(image: Image.Image, name: str, selected_psm: int | None = None) -> str:
            target = work / f"{name}.png"
            preprocess_image(image, mode).save(target)
            return run("tesseract", target.name, "stdout", "-l", language, "--psm", str(selected_psm or psm), cwd=work)

        full_text = ocr(source, "full")
        if format_id.endswith("_th"):
            # Dense table lines interfere with Tesseract's page segmentation.
            # Re-read the sparse identity/footer regions independently and put
            # their higher-resolution candidates first for the field parser.
            width, height = source.size
            header = ocr(source.crop((0, 0, width, round(height * 0.235))), "header", 6)
            footer = ocr(source.crop((0, round(height * 0.82), width, height)), "footer", 6)
            issued = ocr(source.crop((0, round(height * 0.885), round(width * 0.42), round(height * 0.94))), "issued", 7)
            full_text = "\n".join((header, issued, full_text, footer))
        if not format_id.startswith("bachelor_"):
            body = full_text
            if format_id.endswith("_en"):
                return full_text, body
            try:
                from model.cell_ocr import read_course_cells, repair_course_lines
            except ModuleNotFoundError:
                from cell_ocr import read_course_cells, repair_course_lines
            return full_text, repair_course_lines(body, read_course_cells(path, format_id, mode))
        width, height = source.size
        top, bottom = round(height * 0.185), round(height * 0.93)
        middle = width // 2
        body = "\n".join((
            ocr(source.crop((0, top, middle, bottom)), "left"),
            ocr(source.crop((middle, top, width, bottom)), "right"),
        ))
        if format_id.endswith("_en"):
            return full_text, body
        try:
            from model.cell_ocr import read_course_cells, repair_course_lines
        except ModuleNotFoundError:
            from cell_ocr import read_course_cells, repair_course_lines
        return full_text, repair_course_lines(body, read_course_cells(path, format_id, mode))


def value_after(line: str, label: str, stop: str | None = None) -> str | None:
    match = re.search(r"(?:" + label + r")\s*[:：]?\s*(.+)", line, re.I)
    if not match:
        return None
    value = match[1]
    if stop:
        value = re.split(stop, value, maxsplit=1, flags=re.I)[0]
    value = re.split(r"\s{4,}", value, maxsplit=1)[0]
    return value.strip() or None


def date_iso(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r"(\d{1,2})\s+([ก-๙]+|[A-Za-z]+)[,]?\s+(\d{4})", value, re.I)
    if match:
        day, name, year = int(match[1]), match[2], int(match[3])
    else:
        match = re.search(r"([A-Za-z]+)\s+(\d{1,2})[,]?\s+(\d{4})", value, re.I)
        if not match:
            return None
        day, name, year = int(match[2]), match[1], int(match[3])
    month = TH_MONTHS.get(name) or EN_MONTHS.get(name.lower())
    if not month:
        return None
    if year > 2400:
        year -= 543
    return f"{year:04d}-{month:02d}-{day:02d}"


def find_line(lines: list[str], pattern: str) -> str:
    return next((line for line in lines if re.search(pattern, line, re.I)), "")


def detect_format(text: str, override: str | None = None) -> str:
    if override:
        if override not in FORMATS:
            raise ValueError(f"Unknown format: {override}")
        return override
    thai_letters = sum("\u0e00" <= char <= "\u0e7f" for char in text)
    language = "th" if thai_letters > 30 or "ใบแสดงผลการศึกษา" in text or "ภาคการศึกษาที่" in text else "en"
    # Graduate forms have a course-type column (Cr/Nc/Ad), unlike bachelor.
    graduate = bool(re.search(r"\b(?:Cr|Nc|Ad)\s+\d{1,2}\s+[A-FSIBCDU+-]", text, re.I) or re.search(r"ประเภท\s*หน่วยกิต|Type\s+Credit", text, re.I) or re.search(r"Degree\s*:\s*(?:Master|Doctor)|ชื่อปริญญา.*(?:มหาบัณฑิต|ดุษฎีบัณฑิต)", text, re.I))
    return f"{'graduate' if graduate else 'bachelor'}_{language}"


def parse_header(lines: list[str], language: str) -> dict[str, Any]:
    en = language == "en"
    header: dict[str, Any] = {}
    uni_name = next((x.strip() for x in lines if re.search(r"KING MONGKUT|สถาบันเทคโนโลยีพระจอมเกล", x, re.I)), None)
    uni_address = next((x.strip() for x in lines if re.search(r"Chalongkrung Road|เลขท(?:ี่|ี)\s*1\s*ซอยฉลองกรุง", x, re.I)), None)
    header["uni_name"] = "สถาบันเทคโนโลยีพระจอมเกล้าเจ้าคุณทหารลาดกระบัง" if uni_name and not en else uni_name
    header["uni_address"] = "เลขที่ 1 ซอยฉลองกรุง 1 เขตลาดกระบัง กรุงเทพฯ 10520" if uni_address and not en else uni_address
    faculty = find_line(lines, r"(?:^|\s)(College(?:\s+of)?|Faculty(?:\s+of)?|School(?:\s+of)?|International Academy|KMITL Business School|คณะ)")
    if not faculty:
        marker = next((i for i, line in enumerate(lines) if re.search(r"TRANSCRIPT OF RECORDS|ใบแสดงผลการศึกษา", line, re.I)), None)
        if marker is not None:
            faculty = next((line for line in lines[marker + 1:] if line.strip()), "")
    header["faculty_name"] = faculty.strip() or None
    person_label = r"Name(?:\s+of\s+Student)?|Student\s+Name|ชื่อ(?:-สกุล|และนามสกุล|นักศึกษา)?"
    id_label = r"Student\s*(?:ID|No\.?|Number)|Registration\s*(?:ID|No\.?)|รหัส(?:ประจ[ำํา]ตัว)?นักศึกษา"
    person = find_line(lines, person_label)
    person_value = value_after(person, person_label, id_label) or ""
    prefix = re.match(r"(นาย|นางสาว|นาง|Mr\.?|Mrs\.?|Miss)\s*(.*)", person_value, re.I)
    header["prename"] = prefix[1] if prefix else None
    header["name"] = prefix[2] if prefix else person_value or None
    joined = "\n".join(lines)
    sid = re.search(rf"(?:{id_label})\s*[:：#-]?\s*(\d{{8}})", joined, re.I)
    if not sid:
        header_text = "\n".join(lines[: min(30, len(lines))])
        sid = re.search(r"(?<!\d)(\d{8})(?!\d)", header_text)
    header["student_id"] = sid[1] if sid else None
    if header["student_id"]:
        if en:
            header["uni_name"] = "KING MONGKUT'S INSTITUTE OF TECHNOLOGY LADKRABANG"
            header["uni_address"] = "Chalongkrung Road, Ladkrabang, Bangkok 10520, THAILAND"
        else:
            header["uni_name"] = "สถาบันเทคโนโลยีพระจอมเกล้าเจ้าคุณทหารลาดกระบัง"
            header["uni_address"] = "เลขที่ 1 ซอยฉลองกรุง 1 เขตลาดกระบัง กรุงเทพฯ 10520"
    birth = find_line(lines, r"Date of Birth|วันเดือนปีเกิด")
    header["date_of_birth"] = date_iso(value_after(birth, r"Date of Birth|วันเดือนปีเกิด", r"Date of Admission|วันที่เข้าศึกษา"))
    admission = find_line(lines, r"Date of Admission|วันที่เข้าศึกษา")
    header["admis_date"] = date_iso(value_after(admission, r"Date of Admission|วันที่เข้าศึกษา"))
    degree_line = find_line(lines, r"^\s*(Degree|ชื่อปริญญา)")
    header["degree"] = value_after(degree_line, r"Degree|ชื่อปริญญา", r"Date of Graduation|วันที่สำเร็จการศึกษา")
    grad_line = find_line(lines, r"Date of Graduation|วันที่สำเร็จการศึกษา")
    grad_value = value_after(grad_line, r"Date of Graduation|วันที่สำเร็จการศึกษา")
    header["grad_date"] = date_iso(grad_value)
    reason = re.search(r"N/?A\s*(\([^)]*\))", grad_value or "", re.I)
    header["grad_reason"] = f"n/a{reason[1]}" if reason else None
    program_line = find_line(lines, r"^\s*(Program|หลักสูตร)")
    header["program"] = value_after(program_line, r"Program|หลักสูตร")
    header["major"] = None
    honor_line = find_line(lines, r"Honor|เกียรตินิยม")
    header["honor"] = 2 if re.search(r"Second Class|อันดับ\s*2", honor_line, re.I) else (1 if re.search(r"First Class|อันดับ\s*1", honor_line, re.I) else 0)
    return header


def parse_courses(lines: list[str], language: str, graduate: bool) -> list[dict]:
    semesters: list[dict] = []
    current: dict | None = None
    last_course: dict | None = None
    for raw in lines:
        line = raw.strip()
        line = re.sub(r"^(?:Ast|Ist)\s+Semester", "1st Semester", line, flags=re.I)
        line = re.sub(r"\s*[|]\s*", " ", line)
        line = re.sub(r"\bNe\s+(\d{1,2})\s+", r"Nc \1 ", line, flags=re.I)
        if not line:
            continue
        term = parse_term(line, language)
        if term:
            semester, year = term
            current = {"year": year, "sem_num": semester, "GPA": None, "GPS": None, "pass_reason": None, "subject": []}
            semesters.append(current)
            last_course = None
            continue
        special = (EN_SPECIAL if language == "en" else TH_SPECIAL).search(line)
        if special:
            year = int(special[1])
            if language == "en" and year < 2400:
                year += 543
            current = {"year": year, "sem_num": 3, "GPA": None, "GPS": None, "pass_reason": None, "subject": []}
            semesters.append(current)
            last_course = None
            continue
        if re.search(r"รายวิชาเทียบโอน|Transfer(?:red)? Credits", line, re.I):
            current = {"year": None, "sem_num": 0, "GPA": None, "GPS": None, "pass_reason": None, "subject": []}
            semesters.append(current)
            last_course = None
            continue
        # OCR frequently renders grade suffixes as an extra t/c. Correct only
        # these observed glyph confusions, without consulting labels.
        line = re.sub(r"\b([ABCD])t\+\s*$", r"\1+", line, flags=re.I)
        line = re.sub(r"\b([ABCD])t\s*$", r"\1+", line, flags=re.I)
        line = re.sub(r"\b([ABCD])c\s*$", r"\1", line, flags=re.I)
        line = re.sub(r"\bSs\s*$", "S", line, flags=re.I)
        # Low-resolution scanned grade glyphs commonly become digits, while
        # the credit immediately before them remains a single digit.
        line = re.sub(r"(?<=\s)([0-9])\s+0\+\s*$", r"\1 C+", line)
        line = re.sub(r"(?<=\s)([0-9])\s+8\+\s*$", r"\1 B+", line)
        line = re.sub(r"(?<=\s)([0-9])\s+[\(（][๐0]\s*$", r"\1 C", line)
        row = COURSE.match(line) or COURSE_NO_GRADE.match(line)
        if row is None and current is not None and current["sem_num"] == 0:
            transfer = re.match(r"^\s*(\d{8})[.\s]+(.+?)\s+(\d{1,2})[.\s|]+(T\(?[A-FS][+4]?\)?|T[+)]|TB\))\s*$", line, re.I)
            if transfer:
                grade = transfer[4].upper().replace("4", "+")
                if re.fullmatch(r"T[A-FS][+]?\)?", grade):
                    grade = "T(" + grade[1:].rstrip(")") + ")"
                row_data = {"subject_id": transfer[1], "subject_name": transfer[2].strip(), "type": None, "credit": int(transfer[3]), "grade_earn": grade.lower()}
                current["subject"].append(row_data)
                last_course = row_data
                continue
        if row:
            if current is None:
                current = {"year": None, "sem_num": 0, "GPA": None, "GPS": None, "pass_reason": None, "subject": []}
                semesters.append(current)
            last_course = {
                "subject_id": row[1],
                "subject_name": row[2].strip(),
                "type": row[3].lower() if row[3] and graduate else None,
                "credit": int(row[4]),
                "grade_earn": row[5].lower() if row.lastindex == 5 else None,
            }
            current["subject"].append(last_course)
            continue
        if current is None:
            continue
        if re.search(r"คะแนนเฉล(?:ี่|ี)ยประจ(?:ำ|ํา)ภาคการศึกษา|\bGPS\s*:", line, re.I):
            numbers = re.findall(r"(?:\d+\.\d{2}|-)", line)
            if numbers:
                current["GPS"] = "0.00" if numbers[0] == "-" else numbers[0]
            if len(numbers) > 1:
                current["GPA"] = "0.00" if numbers[1] == "-" else numbers[1]
            last_course = None
            continue
        if re.search(r"คะแนนเฉลี่ย\s*:|\bGPA\s*:", line, re.I) and current["GPA"] is None:
            numbers = re.findall(r"(?:\d+\.\d{2}|-)", line)
            if numbers:
                current["GPA"] = None if current["sem_num"] == 0 and numbers[-1] == "-" else ("0.00" if numbers[-1] == "-" else numbers[-1])
            last_course = None
            continue
        if re.search(r"รักษาสภาพ|Maintain", line, re.I):
            current["pass_reason"] = "maintain"
            last_course = None
            continue
        if re.search(r"ลาพัก|Leave of Absence", line, re.I):
            current["pass_reason"] = "leaveofabsence"
            last_course = None
            continue
        # A wrapped course title occupies a line without code/grade. Keep it
        # only directly after a course, before the next semester/summary.
        if last_course and not re.search(r"Total Credits|จำนวนหน่วยกิต|Cumulative GPA|คะแนนเฉลี่ยสะสม|End of Transcript|สิ้นสุดการแสดงผล", line, re.I):
            if not re.match(r"[-=]{3,}|\d{8}", line) and len(line) < 100:
                last_course["subject_name"] += " " + line
        else:
            last_course = None
    # The transfer-credit section precedes the first dated semester; its
    # reference year follows that first dated semester in this document set.
    if semesters and semesters[0]["sem_num"] == 0 and semesters[0]["year"] is None:
        semesters[0]["year"] = next((s["year"] for s in semesters[1:] if s["year"]), None)
    return semesters


def parse_summary(lines: list[str], language: str) -> dict[str, Any]:
    en = language == "en"
    credits_pattern = r"Total Credits Earned|จ(?:ำ|ํา)นวนหน่วยกิตท(?:ี่|ี)สอบได้ทั้งหมด"
    credits_line = find_line(lines, credits_pattern)
    credits_match = re.search(rf"(?:{credits_pattern})\s*[:：]?\s*(\d+)", credits_line, re.I)
    gpa_line = find_line(lines, r"Cumulative GPA|คะแนนเฉล(?:ี่|ี)ยสะสม")
    gpa_match = re.search(r"(\d+\.\d{2})\s*$", gpa_line)
    comp_line = find_line(lines, r"Comprehensive|สอบประมวลความรู้")
    comp = "pass" if re.search(r"\bPass\b|ผ่าน", comp_line, re.I) else None
    return {
        "master_comprehensive": comp,
        "master_thesis": None,
        "master_qualify": None,
        "total_credits_earned": int(credits_match[1]) if credits_match else None,
        "cumulative_gpa": gpa_match[1] if gpa_match else None,
    }


def parse_footer(lines: list[str], language: str) -> dict[str, Any]:
    issued_pattern = r"Date of Issued|วันท(?:ี่|ี)ออกเอกสาร"
    issued = find_line(lines, issued_pattern)
    issued_value = value_after(issued, issued_pattern, r"Not valid|เอกสารจะสมบูรณ์")
    signature = next((x.strip().strip("() ") for x in lines if re.search(r"Test Surname|ทดสอบ\s*นามสกุล", x, re.I)), None)
    position = find_line(lines, r"^\s*(Director|ผู.?อ[ํำ]?านวยการ)")
    registration = find_line(lines, r"KMITL Registration|ทะเบียน.*การศึกษา")
    return {"updated_at": date_iso(issued_value), "by": {"by_signature": signature, "by_position": position.strip() or None, "by_reg": registration.strip() or None}}


def parse(text: str, format_id: str | None = None, body_text: str | None = None) -> dict[str, Any]:
    format_id = detect_format(text, format_id)
    profile = FORMATS[format_id]
    lines = text.splitlines()
    summary = parse_summary(lines, profile["language"])
    summary["semesters"] = parse_courses((body_text or text).splitlines(), profile["language"], profile["course_type_column"])
    return {
        "format_id": format_id,
        "header_detail": parse_header(lines, profile["language"]),
        "transcript_detail": summary,
        "footer_detail": parse_footer(lines, profile["language"]),
    }


def extract(path: Path, format_id: str | None = None, force_ocr: bool = False) -> dict[str, Any]:
    started = time.monotonic()
    path = path.resolve()
    text, engine = read_document(path, force_ocr)
    detected = detect_format(text, format_id)
    if path.suffix.lower() != ".pdf":
        text, body = read_image_profile(path, detected)
        # The inexpensive first pass can miss the graduate course-type column
        # on low-resolution Thai pages.  Re-route once using the clearer
        # profile OCR; an explicit caller override always remains authoritative.
        refined = detect_format(text, format_id)
        if refined != detected:
            detected = refined
            text, body = read_image_profile(path, detected)
    else:
        body = read_bachelor_columns(path, engine, FORMATS[detected]["language"]) if detected.startswith("bachelor_") else None
    candidates = [parse(text, detected, body)]
    if body and body != text:
        candidates.append(parse(text, detected, None))

    def structural_score(candidate: dict[str, Any]) -> tuple[int, int, int]:
        header = candidate.get("header_detail") or {}
        semesters = (candidate.get("transcript_detail") or {}).get("semesters") or []
        courses = sum(len(semester.get("subject") or []) for semester in semesters)
        header_fields = sum(bool(header.get(field)) for field in ("student_id", "name", "faculty_name", "program"))
        dated_semesters = sum(semester.get("year") is not None for semester in semesters)
        return courses, dated_semesters, header_fields

    record = apply_course_catalog(max(candidates, key=structural_score))
    return {"engine": engine, "processing_seconds": round(time.monotonic() - started, 3), "record": record, "validation": validate_record(record)}


def main() -> None:
    arg = argparse.ArgumentParser()
    arg.add_argument("input", type=Path)
    arg.add_argument("--format", choices=sorted(FORMATS))
    arg.add_argument("--force-ocr", action="store_true")
    arg.add_argument("--out", type=Path)
    args = arg.parse_args()
    result = extract(args.input, args.format, args.force_ocr)
    content = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(content, encoding="utf-8")
    else:
        print(content)


if __name__ == "__main__":
    main()
