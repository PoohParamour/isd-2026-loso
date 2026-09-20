"""Position-aware OCR helpers for transcript course tables.

The existing parser remains responsible for document semantics.  This module
uses table geometry only to re-read constrained course cells and repair OCR
lines before parsing.  It never consults labels or file names.
"""

from __future__ import annotations

import csv
import io
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

try:
    from model.extract import preprocess_image
except ModuleNotFoundError:  # Direct execution from model/
    from extract import preprocess_image


@dataclass(frozen=True)
class OCRLine:
    y: float
    text: str


def _tsv_lines(image: Image.Image, language: str, work: Path, name: str) -> list[OCRLine]:
    target = work / f"{name}.png"
    image.save(target)
    result = subprocess.run(
        ["tesseract", target.name, "stdout", "-l", language, "--psm", "6", "tsv"],
        cwd=work,
        capture_output=True,
        text=True,
        check=True,
    )
    groups: dict[tuple[int, int, int, int], list[dict[str, str]]] = {}
    for row in csv.DictReader(io.StringIO(result.stdout), delimiter="\t"):
        text = (row.get("text") or "").strip()
        if row.get("level") != "5" or not text:
            continue
        key = tuple(int(row[field]) for field in ("page_num", "block_num", "par_num", "line_num"))
        groups.setdefault(key, []).append(row)
    lines = []
    for words in groups.values():
        words.sort(key=lambda item: int(item["left"]))
        text = " ".join(item["text"] for item in words)
        y = sum(int(item["top"]) + int(item["height"]) / 2 for item in words) / len(words)
        lines.append(OCRLine(y, text))
    return sorted(lines, key=lambda line: line.y)


def _nearest(lines: list[OCRLine], y: float, tolerance: float = 24) -> str:
    candidates = [line for line in lines if abs(line.y - y) <= tolerance]
    return min(candidates, key=lambda line: abs(line.y - y)).text.strip() if candidates else ""


def _course_code(text: str) -> str | None:
    compact = re.sub(r"\D", "", text)
    return compact if len(compact) == 8 else None


def read_course_cells(path: Path, format_id: str, mode: str) -> dict[str, str]:
    """Return canonical course lines keyed by detected 8-digit course code.

    Column boundaries are proportions of the stable KMITL transcript form,
    applied independently to both page halves.  Reading narrow columns avoids
    the common whole-page failure where credit/grade glyphs attach to titles.
    """
    language = "eng" if format_id.endswith("_en") else "tha+eng"
    graduate = format_id.startswith("graduate_")
    with Image.open(path) as source, tempfile.TemporaryDirectory(prefix="isd_cells_") as temp:
        width, height = source.size
        if width * height > 30_000_000:
            raise ValueError("ภาพมีขนาดพิกเซลเกิน 30 ล้านพิกเซล")
        work = Path(temp)
        top, bottom = round(height * 0.235), round(height * 0.82)
        halves = ((0.04, 0.50), (0.50, 0.96))
        repaired: dict[str, str] = {}
        for side, (start, end) in enumerate(halves):
            span = end - start
            # Relative boundaries inside one half of the table.
            if graduate:
                bounds = {"code": (0.00, 0.14), "name": (0.14, 0.75), "type": (0.75, 0.84), "credit": (0.84, 0.92), "grade": (0.92, 1.00)}
            else:
                bounds = {"code": (0.00, 0.14), "name": (0.14, 0.80), "credit": (0.80, 0.91), "grade": (0.91, 1.00)}
            columns: dict[str, list[OCRLine]] = {}
            for field, (left, right) in bounds.items():
                box = (round(width * (start + span * left)), top, round(width * (start + span * right)), bottom)
                crop = preprocess_image(source.crop(box), mode)
                columns[field] = _tsv_lines(crop, language if field == "name" else "eng", work, f"{side}_{field}")
            for code_line in columns["code"]:
                code = _course_code(code_line.text)
                if not code:
                    continue
                name = _nearest(columns["name"], code_line.y)
                credit_text = _nearest(columns["credit"], code_line.y)
                grade_text = _nearest(columns["grade"], code_line.y)
                credit_match = re.search(r"\d{1,2}", credit_text)
                grade_match = re.search(r"(?:[A-F][+]?|S|I|W|P|NP|U|G|-)", grade_text, re.I)
                if not name or not credit_match or not grade_match:
                    continue
                parts = [code, name]
                if graduate:
                    type_text = _nearest(columns["type"], code_line.y)
                    type_match = re.search(r"Cr|Nc|Ad", type_text, re.I)
                    if not type_match:
                        continue
                    parts.append(type_match.group(0).title())
                parts.extend((credit_match.group(0), grade_match.group(0).upper()))
                repaired[code] = " ".join(parts)
        return repaired


def repair_course_lines(body_text: str, cells: dict[str, str]) -> str:
    """Repair incomplete rows, while preserving already parseable OCR rows."""
    output = []
    for line in body_text.splitlines():
        match = re.search(r"(?<!\d)(\d{8})(?!\d)", line)
        already_structured = re.search(
            r"^\s*\d{8}[.\s]+.+?\s+(?:(?:Cr|Nc|Ad)\s+)?\d{1,2}\s+(?:[A-F][+]?|S|I|W|P|NP|U|G|-)\s*$",
            line,
            re.I,
        )
        output.append(cells.get(match.group(1), line) if match and not already_structured else line)
    return "\n".join(output)
