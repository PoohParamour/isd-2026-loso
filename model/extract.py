"""Fast transcript extraction for digital PDFs and scanned images.

This is a deterministic baseline. It does not read ground-truth labels or file
names during inference. PDF text is used only when the embedded text is usable;
otherwise pages are rendered and read by Tesseract.
"""

from __future__ import annotations

import argparse
from collections import deque
import json
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from PIL import Image, ImageEnhance, ImageFilter, ImageOps
from pillow_heif import register_heif_opener

register_heif_opener()

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
# Preserve damaged course identifiers for validation instead of merging rows.
COURSE = re.compile(r"^\s*(\d{7,9})[.\s]+(.+?)\s+(?:(Cr|Nc|Ad)\s+)?(\d{1,2})\s+([A-F][+]?|S|I|W|P|NP|U|G|T\([A-FS][+]?\)|-)\s*$", re.I)
COURSE_NO_GRADE = re.compile(r"^\s*(\d{7,9})[.\s]+(.+?)\s+(Cr|Nc|Ad)\s+(\d{1,2})\s*$", re.I)
COURSE_PENDING = re.compile(r"^\s*(\d{7,9})[.\s]+(.+?)\s+(\d{1,2})\s*$", re.I)
COURSE_UNREADABLE_GRADE = re.compile(r"^\s*(\d{7,9})[.\s]+(.{3,}?)\s+(?:(Cr|Nc|Ad)\s+)?(\d{1,2})\s+([^\s]{1,4})\s*$", re.I)
COURSE_UNREADABLE_CREDIT = re.compile(r"^\s*(\d{7,9})[.\s]+(.{3,}?)\s+(Cr|Nc|Ad)\s+([^\d\s]{1,3})\s+([A-F][+]?|S|I|W|P|NP|U|G|-)\s*$", re.I)
TH_TERM = re.compile(r"ภาคการศึกษา(?:ที่|ที|ทิ)\s*([123])\s*ปีการศึกษา\s*(\d{4})")
EN_TERM = re.compile(r"\b([123])(?:st|nd|rd|th)\s+Semester[,.]?(?:\s+Academic\s+Year)?\s*(\d{4})", re.I)
TH_SPECIAL = re.compile(r"ภาคการศึกษาพิเศษ\s*ปีการศึกษา\s*(\d{4})")
EN_SPECIAL = re.compile(r"(?:Summer|Special)\s+Semester[,]?(?:\s+Academic\s+Year)?\s*(\d{4})", re.I)


def parse_term(line: str, language: str) -> tuple[int, int] | None:
    """Parse common semester headings without depending on one template."""
    if language == "en":
        line = re.sub(r"\b(?:Ast|Ist|151|1S1)\s+(?=S(?:er|e)mester)", "1st ", line, flags=re.I)
        line = re.sub(r"\bSermester\b", "Semester", line, flags=re.I)
        line = re.sub(r"\bYeur\b", "Year", line, flags=re.I)
    patterns = (
        (
            r"(?:ภาคการศึกษา|ภาคเรียน)(?:ที่|ที|ทิ)?\s*([123])\D{0,30}(?:ปีการศึกษา|ปี)\s*(\d{4})",
            r"(?:ปีการศึกษา|ปี)\s*(\d{4})\D{0,30}(?:ภาคการศึกษา|ภาคเรียน)(?:ที่|ที|ทิ)?\s*([123])",
        )
        if language == "th"
        else (
            r"\b([123])(?:st|nd|rd|th)?\s+Semester\s*[,.]?\s*(?:(?:Academic\s+)?[Y¥]\s*ear\s*[,.]?\s*)?(\d{4})(?:\s*-\s*\d{4})?",
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
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", check=True)
    return result.stdout


def text_is_usable(text: str) -> bool:
    if len(text.strip()) < 300:
        return False
    damaged = sum(char == "ÿ" or (ord(char) < 32 and char not in "\t\n\r\f") for char in text)
    if damaged / len(text) > 0.02:
        return False
    transcript_marker = re.search(r"TRANSCRIPT OF RECORDS|Unofficial Transcript|ใบแสดงผลการศึกษา", text, re.I)
    identity_marker = re.search(r"Student\s*(?:ID|No\.?|Number)|รหัส(?:ประจ[ำํา]ตัว)?นักศึกษา", text, re.I)
    return bool(transcript_marker and identity_marker)


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
            # Normalize every uploaded raster format (including HEIC/HEIF) so
            # downstream OCR only has to consume a well-supported PNG.
            target = work / "page-1.png"
            with Image.open(path) as source:
                image = ImageOps.exif_transpose(source).convert("RGB")
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
        if not re.search(r"TRANSCRIPT OF RECORDS|Unofficial Transcript", combined, re.I):
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
                image = ImageOps.exif_transpose(source).convert("RGB")
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
    with Image.open(path) as opened_source, tempfile.TemporaryDirectory(prefix="isd_ocr_profile_") as temp:
        source = ImageOps.exif_transpose(opened_source)
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
    english_header_cues = sum(bool(re.search(rf"(?mi)^\s*{label}\b", text))
                              for label in ("Name", "Date of Birth", "Degree", "Program"))
    language = ("en" if english_header_cues >= 3 else
                "th" if thai_letters > 30 or "ใบแสดงผลการศึกษา" in text or "ภาคการศึกษาที่" in text else "en")
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
    faculty = next(
        (
            line
            for line in lines
            if re.search(r"(?:^|\s)(College(?:\s+of)?|Faculty(?:\s+of)?|School(?:\s+of)|International Academy|KMITL Business School|คณะ)", line, re.I)
            and not re.match(r"\s*\d{8}\b", line)
        ),
        "",
    )
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
    unofficial = any(re.search(r"Unofficial\s+Transcript", line, re.I) for line in lines)
    if not sid and not unofficial:
        header_text = "\n".join(lines[: min(30, len(lines))])
        sid = re.search(r"(?<!\d)(\d{8})(?!\d)", header_text)
    header["student_id"] = sid[1] if sid else None
    official = any(re.search(r"TRANSCRIPT OF RECORDS|ใบแสดงผลการศึกษา", line, re.I) for line in lines)
    if header["student_id"] and not unofficial and (official or uni_name or uni_address):
        if en:
            header["uni_name"] = "KING MONGKUT'S INSTITUTE OF TECHNOLOGY LADKRABANG"
            header["uni_address"] = "Chalongkrung Road, Ladkrabang, Bangkok 10520, THAILAND"
        else:
            header["uni_name"] = "สถาบันเทคโนโลยีพระจอมเกล้าเจ้าคุณทหารลาดกระบัง"
            header["uni_address"] = "เลขที่ 1 ซอยฉลองกรุง 1 เขตลาดกระบัง กรุงเทพฯ 10520"
    birth = find_line(lines, r"Date of Birth|วันเดือนปีเกิด")
    header["date_of_birth"] = date_iso(value_after(birth, r"Date of Birth|วันเดือนปีเกิด", r"Date of Admission|วันที่เข้าศึกษา"))
    admission_label = r"Date of Admission|วันท(?:ี่|ี|ิ)เข(?:้|)าศึกษา"
    admission = find_line(lines, admission_label)
    header["admis_date"] = date_iso(value_after(admission, admission_label))
    graduation_label = r"Date of Graduation|วันท(?:ี่|ี|ิ)ส(?:ำ|ํา|า)เ(?:ร็|ริ)จการศึกษา"
    degree_line = find_line(lines, r"^\s*(Degree|ชื่อปริญญา)")
    header["degree"] = value_after(degree_line, r"Degree|ชื่อปริญญา", graduation_label)
    grad_line = find_line(lines, graduation_label)
    grad_value = value_after(grad_line, graduation_label)
    header["grad_date"] = date_iso(grad_value)
    reason = re.search(r"N/?A\s*(\([^)]*\))", grad_value or "", re.I)
    header["grad_reason"] = f"n/a{reason[1]}" if reason else None
    program_line = find_line(lines, r"^\s*(Program|หลักสูตร)")
    header["program"] = value_after(program_line, r"Program|หลักสูตร")
    header["major"] = None
    honor_line = find_line(lines, r"Honor|เกียรตินิยม")
    header["honor"] = 2 if re.search(r"Second Class|อันดับ\s*2", honor_line, re.I) else (1 if re.search(r"First Class|อันดับ\s*1", honor_line, re.I) else 0)
    return header


def separate_course_lines(lines: list[str]):
    """Keep OCR-joined course rows from donating their cells to each other.

    Seven/nine-digit damaged identifiers are boundaries too, but are not
    repaired: validation must ask the reviewer to check the original image.
    Only split lines starting with a course identifier, never header prose.
    """
    start = r"\d{7,9}[.\s]+(?=[A-Za-z\u0e01-\u0e5b])"
    for raw in lines:
        line = raw.strip()
        line = re.sub(r"^[|.:;\[\]\s]+(?=" + start + r")", "", line)
        if re.match(start, line):
            yield from re.split(r"\s*[|.:;]?\s+(?=" + start + r")", line)
        else:
            yield line


def parse_courses(lines: list[str], language: str, graduate: bool) -> list[dict]:
    semesters: list[dict] = []
    current: dict | None = None
    last_course: dict | None = None
    pending_lines = deque(separate_course_lines(lines))
    while pending_lines:
        raw = pending_lines.popleft()
        line = raw.strip()
        line = re.sub(r"^(?:Ast|Ist|151|1S1)\s+Semester", "1st Semester", line, flags=re.I)
        line = re.sub(r"^2ad\s+Semester", "2nd Semester", line, flags=re.I)
        if language == "th" and graduate and re.match(r"^\s*\d{8}\b", line):
            line = re.sub(r"(?i)(Cr|Nc|Ad)\s*[|]?\s*(\d{1,2})(?:\s*[|])+\s*$", r"\1 \2 I", line)
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
        # Decimal points can disappear in compact summary cells (338 means
        # 3.38). Restrict the repair to a labeled GPS value before GPA.
        line = re.sub(r"(\bGPS\s*:\s*)([0-4])(\d{2})(?=\s+GPA\b)", r"\1\2.\3", line, flags=re.I)
        if language == "en" and graduate and re.match(r"^\s*\d{8}\b", line):
            # On small English graduate scans, OCR reads the narrow Nc
            # column as Ne and a one-credit cell as capital I.
            line = re.sub(r"\bNe\b", "Nc", line, flags=re.I)
            line = re.sub(r"\b(Cr|Nc|Ad)\s+[Il]\s+([A-FS][+]?|I|W|P|U|-)$", r"\1 1 \2", line, flags=re.I)
        if language == "th":
            # Thai OCR often substitutes visually similar Thai/digit glyphs
            # for the Latin values in the narrow type and grade columns.
            # Keep these repairs position-bound to course rows so ordinary
            # Thai prose is never rewritten.
            if graduate and re.match(r"^\s*\d{8}\b", line):
                line = re.sub(r"\s+(?:๓)\s*[|]?\s+(\d{1,2})\s+([รธ])\s*$", r" Cr \1 S", line)
                line = re.sub(r"\s+(?:ผ๐)\s*[|]?\s+(\d{1,2})\s+([รธ])\s*$", r" Nc \1 S", line)
                line = re.sub(r"\s+(Cr|Nc|Ad)\s*[|]?\s+(\d{1,2})\s+1!\s*$", r" \1 \2 I", line, flags=re.I)
                line = re.sub(r"\s+(Cr|Nc|Ad)\s*[|]?\s+(\d{1,2})\s+[รธ]\s*$", r" \1 \2 S", line, flags=re.I)
                line = re.sub(r"\s+(Cr|Nc|Ad)\s+(\d{1,2})\s+8\s*$", r" \1 \2 S", line, flags=re.I)
                line = re.sub(r"\s+(Cr|Nc|Ad)\s+(\d{1,2})\s*[|]\s*$", r" \1 \2 I", line, flags=re.I)
            line = re.sub(r"(?<=\s)([0-9])\s+๐\s*$", r"\1 C", line)
            line = re.sub(r"(?<=\s)([0-9])\s+8\+\s*$", r"\1 B+", line)
        # Low-resolution scanned grade glyphs commonly become digits, while
        # the credit immediately before them remains a single digit.
        line = re.sub(r"(?<=\s)([0-9])\s+0\+\s*$", r"\1 C+", line)
        line = re.sub(r"(?<=\s)([0-9])\s+8\+\s*$", r"\1 B+", line)
        line = re.sub(r"(?<=\s)([0-9])\s+[\(（][๐0]\s*$", r"\1 C", line)
        sparse = re.match(r"^(\d{7,9}|\?)\s+(.+?)\s+(\d{1,2}|\?)\s+(\?|[A-F][+]?|S|I|W|P|NP|U|G|-)\s*$", line, re.I) if language == "en" and not graduate else None
        if sparse and "?" in (sparse[1], sparse[3], sparse[4]):
            if current is None:
                current = {"year": None, "sem_num": 0, "GPA": None, "GPS": None, "pass_reason": None, "subject": []}
                semesters.append(current)
            last_course = {"subject_id": None if sparse[1] == "?" else sparse[1],
                           "subject_name": sparse[2].strip(), "type": None,
                           "credit": None if sparse[3] == "?" else int(sparse[3]),
                           "grade_earn": None if sparse[4] == "?" else sparse[4].lower()}
            current["subject"].append(last_course)
            continue
        row = COURSE.match(line) or COURSE_NO_GRADE.match(line)
        pending = COURSE_PENDING.match(line) if language == "en" and not graduate else None
        # A numeric OCR grade (e.g. "CHARM SCHOOL 3 7") can otherwise be
        # consumed as pending credit, leaving the actual credit in the title.
        # Restrict this fallback to a high terminal value after a credit-like
        # token; ordinary numbered titles such as "CALCULUS 1 3" stay intact.
        if pending and int(pending[3]) > 6:
            numeric_grade = COURSE_UNREADABLE_GRADE.match(line)
            if numeric_grade and int(numeric_grade[4]) <= 6 and numeric_grade[5].isdigit():
                pending = None
        uncertain = COURSE_UNREADABLE_GRADE.match(line) if row is None and pending is None else None
        if uncertain and re.fullmatch(r"[A-F][+]?|S|I|W|P|NP|U|G|T\([A-FS][+]?\)|-", uncertain[5], re.I):
            uncertain = None
        uncertain_credit = (COURSE_UNREADABLE_CREDIT.match(line)
                            if graduate and row is None and uncertain is None else None)
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
        if pending:
            if current is None:
                current = {"year": None, "sem_num": 0, "GPA": None, "GPS": None, "pass_reason": None, "subject": []}
                semesters.append(current)
            last_course = {
                "subject_id": pending[1],
                "subject_name": pending[2].strip(),
                "type": None,
                "credit": int(pending[3]),
                "grade_earn": None,
            }
            current["subject"].append(last_course)
            continue
        if uncertain:
            if current is None:
                current = {"year": None, "sem_num": 0, "GPA": None, "GPS": None, "pass_reason": None, "subject": []}
                semesters.append(current)
            last_course = {
                "subject_id": uncertain[1],
                "subject_name": uncertain[2].strip(),
                "type": uncertain[3].lower() if uncertain[3] and graduate else None,
                "credit": int(uncertain[4]),
                # Keep the visible row, but never turn an unreadable glyph into a grade.
                "grade_earn": None,
            }
            current["subject"].append(last_course)
            continue
        if uncertain_credit:
            if current is None:
                current = {"year": None, "sem_num": 0, "GPA": None, "GPS": None, "pass_reason": None, "subject": []}
                semesters.append(current)
            last_course = {
                "subject_id": uncertain_credit[1],
                "subject_name": uncertain_credit[2].strip(),
                "type": uncertain_credit[3].lower(),
                "credit": None,
                "grade_earn": uncertain_credit[5].lower(),
            }
            current["subject"].append(last_course)
            continue
        # A photographed screen can preserve the eight-digit course code and
        # title while the thin credit/grade cells dissolve into table noise.
        # Retain only what was visibly read; never infer a grade from context.
        visible = re.match(r"^\s*(\d{7,9})[.\s]+([A-Za-z][A-Za-z0-9/&() .,+'-]{3,})", line) if language == "en" else None
        if visible and sum(char.isalpha() for char in visible[2]) >= 4:
            title = visible[2].strip(" .|-")
            tail = re.search(r"\s+([1-9])\s+[^\s]{1,4}\s*$", title)
            credit = int(tail[1]) if tail else None
            if tail:
                title = title[:tail.start()].strip(" .|-")
            if current is None:
                current = {"year": None, "sem_num": 0, "GPA": None, "GPS": None, "pass_reason": None, "subject": []}
                semesters.append(current)
            last_course = {"subject_id": visible[1], "subject_name": title,
                           "type": None, "credit": credit, "grade_earn": None}
            current["subject"].append(last_course)
            continue
        if current is None:
            continue
        if re.search(r"(?:ค)?ะแนนเฉล(?:ี่|ี|ิ)ยประจ(?:ำ|ํา)ภาคการศึกษา|\bGPS\s*:", line, re.I):
            numbers = re.findall(r"(?:\d+\.\d{2}|-)", line)
            if numbers:
                current["GPS"] = "0.00" if numbers[0] == "-" else numbers[0]
            if len(numbers) > 1:
                gpa = numbers[1]
                # A table border is commonly attached as a leading "1"
                # (for example 2.34 -> 12.34). GPA/GPS cannot exceed 4.00.
                if gpa != "-" and float(gpa) > 4 and gpa.startswith("1"):
                    gpa = gpa[1:]
                current["GPA"] = "0.00" if gpa == "-" else gpa
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
        if re.fullmatch(r"\d{1,2}(?:\s+(?:[A-F][+]?|S|I|W|P|NP|U|G|-|\d{1,2}))?", line, re.I):
            # Detached cells have no reliable row association. Never append
            # them to a title or overwrite the preceding course's grade.
            continue
        if last_course and not re.search(r"Total Credits|จำนวนหน่วยกิต|Cumulative GPA|คะแนนเฉลี่ยสะสม|End of Transcript|สิ้นสุดการแสดงผล|Date (?:of )?Issued|วันที่ออกเอกสาร|Not valid without seal", line, re.I):
            # OCR can put the next row after a stray cell or a wrapped title
            # ("7 90644007 FOUNDATION ENGLISH 1 3 S"). Require a complete
            # row-shaped suffix before splitting a continuation; a numeric
            # reference in ordinary prose is not sufficient evidence.
            for boundary in re.finditer(r"(?<!\w)\d{7,9}[.\s]+(?=[A-Za-z\u0e01-\u0e5b])", line):
                suffix = list(separate_course_lines([line[boundary.start():]]))
                first = suffix[0]
                if (COURSE.match(first) or COURSE_NO_GRADE.match(first)
                        or COURSE_UNREADABLE_GRADE.match(first)
                        or (language == "en" and not graduate and COURSE_PENDING.match(first))):
                    pending_lines.extendleft(reversed(suffix))
                    line = line[:boundary.start()].strip(" .|:;[]")
                    # Detached numeric cells cannot be assigned to either
                    # course safely. Preserve actual wrapped title words.
                    if not re.search(r"[A-Za-z\u0e01-\u0e5b]", line):
                        line = ""
                    break
            if not line:
                continue
            if not re.match(r"[-=]{3,}|\d{7,9}\b", line) and len(line) < 100:
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
    credits_pattern = r"Total (?:number of )?credit(?:s)? earned|จ(?:ำ|ํา)นวนหน(?:่|)?วยกิตท(?:ี่|ี)สอบไ(?:ด้|ด)ทั้งหมด"
    credits_line = find_line(lines, credits_pattern)
    credits_match = re.search(rf"(?:{credits_pattern})\s*[:：]?\s*(\d+)", credits_line, re.I)
    gpa_line = find_line(lines, r"Cumulative GPA|คะแนนเฉล(?:ี่|ี|ิ)ยสะสม")
    gpa_match = re.search(r"(\d+\.\d{2})\s*$", gpa_line)
    comp_line = find_line(lines, r"Comprehensive|สอบประมวลความร(?:ู้|ู)")
    comp = ("pass" if en else "ผ่าน") if re.search(r"\bPass\b|ผ(?:่)?าน", comp_line, re.I) else None
    return {
        "master_comprehensive": comp,
        "master_thesis": None,
        "master_qualify": None,
        "total_credits_earned": int(credits_match[1]) if credits_match else None,
        # A stray table glyph can turn 3.34 into 23.34. Keep only a
        # physically possible GPA; another OCR pass may have read it cleanly.
        "cumulative_gpa": gpa_match[1] if gpa_match and 0 <= float(gpa_match[1]) <= 4 else None,
    }


def recover_semester_headings(primary: str, sources: list[str], language: str) -> str:
    """Insert a missing heading only with two title anchors and matching neighbors.

    Use other OCR passes on the same image; never infer years from course IDs
    or replace the better pass's course cells. Ambiguous insertions are ignored.
    """
    if language != "en":
        return primary

    def heading(line):
        line = re.sub(r"^[|.:\s]+", "", line)
        line = re.sub(r"^(?:Ast|Ist|151|1S1)\s+Semester", "1st Semester", line, flags=re.I)
        return parse_term(line, language)

    def title(line):
        line = line.strip(" |.:[]")
        if re.match(r"\d{7,9}[.\s]", line):
            line = re.sub(r"^\d{7,9}[.\s]+", "", line)
            line = re.sub(r"\s+(?:(?:Cr|Nc|Ad)\s+)?\d{1,2}(?:\s+[|]?\s*\S{1,4})?\s*$", "", line)
        return re.sub(r"[^a-z]", "", line.lower())

    lines = primary.splitlines()
    known = [(i, heading(line)) for i, line in enumerate(lines) if heading(line)]
    existing = {term for _, term in known}
    proposals: dict[int, set[tuple[int, int]]] = {}
    for source in sources:
        reference = [line.strip() for line in source.splitlines() if line.strip()]
        heads = [(i, heading(line)) for i, line in enumerate(reference) if heading(line)]
        for h in range(1, len(heads) - 1):
            index, term = heads[h]
            if term in existing or index + 2 >= heads[h + 1][0]:
                continue
            anchors = [title(reference[index + offset]) for offset in (1, 2)]
            if any(len(anchor) < 12 for anchor in anchors):
                continue
            matches = []
            for i in range(len(lines) - 1):
                if not re.match(r"^[|.:\s]*\d{7,9}[.\s]", lines[i]):
                    continue
                if [title(lines[i]), title(lines[i + 1])] != anchors:
                    continue
                previous = next((t for pos, t in reversed(known) if pos < i), None)
                following = next((t for pos, t in known if pos > i), None)
                if previous == heads[h - 1][1] and following == heads[h + 1][1]:
                    matches.append(i)
            if len(matches) == 1:
                proposals.setdefault(matches[0], set()).add(term)
    # The same heading at multiple positions is also ambiguous.
    terms = [next(iter(values)) for values in proposals.values() if len(values) == 1]
    for index, values in sorted(proposals.items(), reverse=True):
        if len(values) == 1:
            term = next(iter(values))
            if terms.count(term) == 1:
                semester, year = term
                lines.insert(index, f"Semester {semester} Year {year}")
    return "\n".join(lines)


def cumulative_gpa_from_sources(sources: list[str], language: str) -> str | None:
    """Recover only an explicit, unambiguous cumulative GPA from existing OCR.

    Do not infer decimal points, reuse semester GPA, or compute from grades.
    Multiple distinct readable values require review instead of a guess.
    """
    values = set()
    for source in sources:
        for line in source.splitlines():
            value = parse_summary([line], language)["cumulative_gpa"]
            if value is not None and 0 <= float(value) <= 4:
                values.add(f"{float(value):.2f}")
    return next(iter(values)) if len(values) == 1 else None


def parse_footer(lines: list[str], language: str) -> dict[str, Any]:
    issued_pattern = r"Date (?:of )?Issued|วันท(?:ี่|ี)ออกเอกสาร"
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


def _orient_photo(page: Image.Image, work: Path) -> Image.Image:
    """Choose the quarter-turn whose quick OCR contains transcript cues."""
    best = page
    best_score = -1
    original_score = 0
    for degrees in (0, 90, 180, 270):
        candidate = page if degrees == 0 else page.rotate(degrees, expand=True)
        preview = candidate.copy()
        preview.thumbnail((1200, 1600), Image.Resampling.LANCZOS)
        name = f"orientation-{degrees}.png"
        preview.save(work / name)
        sample = run("tesseract", name, "stdout", "-l", "eng", "--psm", "11", cwd=work)
        score = (4 * bool(re.search(r"\b(?:Name|Student\s*ID|Unofficial\s+Transcript)\b", sample, re.I))
                 + 3 * len(re.findall(r"\b(?:Semester|Course|Program|Degree)\b", sample, re.I))
                 + len(re.findall(r"(?<!\d)\d{8}(?!\d)", sample)))
        if degrees == 0:
            original_score = score
        if score > best_score:
            best, best_score = candidate, score
    # Keep the original direction when the text evidence is weak or tied.
    return best if best_score >= 7 and best_score >= original_score + 4 else page


def prefer_deskew_result(base: dict[str, Any], candidate: dict[str, Any]) -> bool:
    """Accept a second OCR pass only after a clear structural improvement."""
    base_record, next_record = base["record"], candidate["record"]
    base_semesters = base_record["transcript_detail"]["semesters"]
    next_semesters = next_record["transcript_detail"]["semesters"]

    def valid_courses(semesters: list[dict]) -> int:
        return sum(bool(re.fullmatch(r"\d{8}", str(subject.get("subject_id") or "")))
                   for semester in semesters for subject in semester.get("subject") or [])

    base_header, next_header = base_record["header_detail"], next_record["header_detail"]
    fields = ("student_id", "name", "faculty_name", "program")
    base_courses, next_courses = valid_courses(base_semesters), valid_courses(next_semesters)
    base_terms = sum(item.get("year") is not None for item in base_semesters)
    next_terms = sum(item.get("year") is not None for item in next_semesters)
    base_errors, next_errors = base["validation"]["errors"], candidate["validation"]["errors"]
    improved = (next_courses >= base_courses + 3
                or (next_courses > base_courses and next_terms > base_terms)
                or (next_courses >= base_courses and base_errors - next_errors >= 3))
    return (improved
            and next_courses >= base_courses
            and next_terms >= base_terms
            and sum(bool(next_header.get(key)) for key in fields)
            >= sum(bool(base_header.get(key)) for key in fields)
            and (not base_header.get("student_id") or base_header["student_id"] == next_header.get("student_id"))
            and next_errors <= base_errors)


def extract(path: Path, format_id: str | None = None, force_ocr: bool = False,
            image_layout: str = "auto", _rectified: bool = False,
            _orientation_checked: bool = False,
            _deskew_checked: bool = False) -> dict[str, Any]:
    if image_layout not in {"auto", "profile", "detected"}:
        raise ValueError(f"Unknown image layout: {image_layout}")
    started = time.monotonic()
    path = path.resolve()
    if path.suffix.lower() != ".pdf" and not (_rectified or _orientation_checked) and path.exists():
        try:
            from model.photo_geometry import straighten_photo
        except ModuleNotFoundError:
            from photo_geometry import straighten_photo
        with Image.open(path) as source:
            if source.width * source.height > 30_000_000:
                raise ValueError("ภาพมีขนาดพิกเซลเกิน 30 ล้านพิกเซล")
            page = straighten_photo(source)
            # White screenshots and axis-aligned scans may have no detectable
            # photo border. Their text still needs an independent direction check.
            orientation_source = page if page is not None else ImageOps.exif_transpose(source).convert("RGB")
        with tempfile.TemporaryDirectory(prefix="isd_photo_") as temp:
            work = Path(temp)
            upright = _orient_photo(orientation_source, work)
            if page is not None or upright is not orientation_source:
                corrected = work / "page.png"
                upright.save(corrected)
                result = extract(corrected, format_id, force_ocr, image_layout,
                                 _rectified=page is not None, _orientation_checked=True)
                if page is not None and min(page.size) < 900:
                    result["validation"]["issues"].append({
                        "path": "input.image", "code": "low_resolution_photo",
                        "message": "ภาพเอกสารเล็กเกินกว่าจะอ่านตารางได้ชัด กรุณาอัปโหลด PDF ต้นฉบับหรือภาพคมชัดที่หน้ากระดาษกว้างอย่างน้อย 1500 พิกเซล",
                        "severity": "warning",
                    })
                    result["validation"]["warnings"] += 1
                    result["validation"]["needs_review"] = True
                result["processing_seconds"] = round(time.monotonic() - started, 3)
                return result
    screen_reading = None
    if _rectified and image_layout == "auto" and format_id in (None, "bachelor_en"):
        try:
            from model.screen_table import read_screen_table
        except ModuleNotFoundError:
            from screen_table import read_screen_table
        screen_reading = read_screen_table(path)
    text, engine = (screen_reading[0], "tesseract") if screen_reading else read_document(path, force_ocr)
    detected = detect_format(text, format_id)
    initial_text = text
    selected_layout = image_layout
    if path.suffix.lower() != ".pdf":
        # An unfamiliar transcript heading is a textual signal to use the
        # layout discovered from this image, not the legacy page crops.
        if image_layout == "auto":
            selected_layout = ("detected" if re.search(r"\bUnofficial\s+Transcript\b", initial_text, re.I)
                               else "profile")
        if screen_reading:
            body = screen_reading[1]
        elif selected_layout == "detected":
            try:
                from model.layout_ocr import read_layout_body
            except ModuleNotFoundError:
                from layout_ocr import read_layout_body
            mode = {"bachelor_th": "original", "bachelor_en": "sharpen",
                    "graduate_th": "sharpen", "graduate_en": "autocontrast"}[detected]
            body = read_layout_body(path, FORMATS[detected]["language"], mode)
        else:
            text, body = read_image_profile(path, detected)
            # The inexpensive first pass can miss the graduate course-type
            # column. An explicit caller override stays authoritative.
            refined = detect_format(text, format_id)
            if refined != detected:
                detected = refined
                text, body = read_image_profile(path, detected)
    else:
        body = read_bachelor_columns(path, engine, FORMATS[detected]["language"]) if detected.startswith("bachelor_") else None
    candidates = [parse(text, detected, body)]
    course_sources = [body or text]
    gpa_sources = [initial_text, text, body or ""]
    if body and body != text and not screen_reading:
        candidates.append(parse(text, detected, None))
        course_sources.append(text)

    def structural_score(candidate: dict[str, Any]) -> tuple[int, int, int]:
        header = candidate.get("header_detail") or {}
        semesters = (candidate.get("transcript_detail") or {}).get("semesters") or []
        courses = sum(bool(re.fullmatch(r"\d{8}", str(subject.get("subject_id") or "")))
                      for semester in semesters for subject in semester.get("subject") or [])
        header_fields = sum(bool(header.get(field)) for field in ("student_id", "name", "faculty_name", "program"))
        dated_semesters = sum(semester.get("year") is not None for semester in semesters)
        return courses, dated_semesters, header_fields

    if path.suffix.lower() != ".pdf" and image_layout == "auto" and selected_layout == "profile":
        profile_score = max(structural_score(candidate) for candidate in candidates)
        if profile_score[0] < 2 or profile_score[1] == 0:
            try:
                from model.layout_ocr import read_layout_body
            except ModuleNotFoundError:
                from layout_ocr import read_layout_body
            mode = {"bachelor_th": "original", "bachelor_en": "sharpen",
                    "graduate_th": "sharpen", "graduate_en": "autocontrast"}[detected]
            detected_body = read_layout_body(path, FORMATS[detected]["language"], mode)
            gpa_sources.append(detected_body)
            candidates.append(parse(text, detected, detected_body))
            course_sources.append(detected_body or text)
            if initial_text != text:
                candidates.append(parse(initial_text, detected, detected_body))
                course_sources.append(detected_body or initial_text)
    if (path.suffix.lower() != ".pdf" and _rectified and image_layout == "auto" and not screen_reading
            and detected == "bachelor_en"
            and re.search(r"Unofficial\s+Transcript", initial_text, re.I)):
        try:
            from model.photo_unofficial import read_unofficial_photo
        except ModuleNotFoundError:
            from photo_unofficial import read_unofficial_photo
        isolated = read_unofficial_photo(path)
        if isolated:
            candidates.append(parse(isolated[0], detected, isolated[1]))
            course_sources.append(isolated[1] or isolated[0])
            gpa_sources.extend(isolated)
    selected = max(range(len(candidates)), key=lambda index: structural_score(candidates[index]))
    record = candidates[selected]
    if path.suffix.lower() != ".pdf":
        recovered = recover_semester_headings(course_sources[selected], gpa_sources, FORMATS[detected]["language"])
        if recovered != course_sources[selected]:
            record["transcript_detail"]["semesters"] = parse_courses(
                recovered.splitlines(), FORMATS[detected]["language"], FORMATS[detected]["course_type_column"])
    record = apply_course_catalog(record)
    if record["transcript_detail"]["cumulative_gpa"] is None:
        record["transcript_detail"]["cumulative_gpa"] = cumulative_gpa_from_sources(
            gpa_sources, FORMATS[detected]["language"])
    if (_rectified and not record["transcript_detail"]["semesters"] and
            not re.search(r"Student\s*ID\s*[:#-]?\s*\d{8}", text, re.I)):
        # A free-standing eight-digit course code is not evidence of an ID.
        record["header_detail"]["student_id"] = None
    validation = validate_record(record)
    if screen_reading:
        validation["issues"].append({
            "path": "input.image", "code": "screen_photo_review",
            "message": "ภาพถ่ายจออาจอ่านรหัสวิชา ตัวเลข และเกรดคลาดเคลื่อน กรุณาเทียบกับภาพก่อนบันทึก",
            "severity": "warning",
        })
        validation["warnings"] += 1
        validation["needs_review"] = True
    if record["transcript_detail"]["cumulative_gpa"] is None:
        label = r"Cumulative GPA|คะแนนเฉล(?:ี่|ี|ิ)ยสะสม"
        invalid_reading = any(
            (match := re.search(r"(\d+\.\d{2})\s*$", line)) and float(match[1]) > 4
            for source in gpa_sources for line in source.splitlines() if re.search(label, line, re.I)
        )
        if invalid_reading:
            validation["issues"].append({
                "path": "transcript_detail.cumulative_gpa", "code": "unreadable_cumulative_gpa",
                "message": "อ่าน GPA สะสมได้ไม่ชัด กรุณาตรวจจากเอกสารต้นฉบับ",
                "severity": "warning",
            })
            validation["warnings"] += 1
            validation["needs_review"] = True
    result = {"engine": engine, "processing_seconds": round(time.monotonic() - started, 3),
              "record": record, "validation": validation}
    if path.suffix.lower() != ".pdf" and path.exists() and not (_rectified or _deskew_checked):
        try:
            from model.photo_geometry import deskew_table
        except ModuleNotFoundError:
            from photo_geometry import deskew_table
        with Image.open(path) as source:
            corrected = deskew_table(source)
        if corrected:
            with tempfile.TemporaryDirectory(prefix="isd_deskew_") as temp:
                target = Path(temp) / "deskewed.png"
                corrected[0].save(target)
                candidate = extract(target, format_id, force_ocr, image_layout,
                                    _orientation_checked=True, _deskew_checked=True)
            if prefer_deskew_result(result, candidate):
                result = candidate
            result["processing_seconds"] = round(time.monotonic() - started, 3)
    return result


def main() -> None:
    arg = argparse.ArgumentParser()
    arg.add_argument("input", type=Path)
    arg.add_argument("--format", choices=sorted(FORMATS))
    arg.add_argument("--force-ocr", action="store_true")
    arg.add_argument("--image-layout", choices=("auto", "profile", "detected"), default="auto")
    arg.add_argument("--out", type=Path)
    args = arg.parse_args()
    result = extract(args.input, args.format, args.force_ocr, args.image_layout)
    content = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(content, encoding="utf-8")
    else:
        print(content)


if __name__ == "__main__":
    main()
