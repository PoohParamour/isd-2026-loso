"""Find transcript reading columns from OCR evidence rather than page coordinates."""

from __future__ import annotations

import csv
import io
import re
import statistics
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps


@dataclass(frozen=True)
class CodeBox:
    left: int
    top: int
    width: int
    height: int


def _code_boxes(tsv: str) -> list[CodeBox]:
    boxes = []
    for word in csv.DictReader(io.StringIO(tsv), delimiter="\t"):
        token = (word.get("text") or "").strip("|.:,;[]() ")
        if word.get("level") != "5" or not re.fullmatch(r"\d{8}", token):
            continue
        try:
            boxes.append(CodeBox(*(int(word[key]) for key in ("left", "top", "width", "height"))))
        except (KeyError, TypeError, ValueError):
            continue
    return boxes


def _column_starts(boxes: list[CodeBox]) -> list[int]:
    """Cluster repeated course-code x positions; isolated IDs are ignored."""
    if len(boxes) < 2:
        return []
    median_width = statistics.median(box.width for box in boxes)
    groups: list[list[CodeBox]] = []
    for box in sorted(boxes, key=lambda item: item.left):
        if not groups or box.left - statistics.median(item.left for item in groups[-1]) > median_width * 2:
            groups.append([box])
        else:
            groups[-1].append(box)
    repeated = [group for group in groups if len(group) >= 2]
    return [round(statistics.median(item.left for item in group)) for group in repeated]


def read_layout_body(path: Path, language: str, mode: str) -> str:
    """OCR columns discovered by repeated course codes, in reading order.

    No field is assigned to a preselected part of the page. When there is no
    repeated code alignment, OCR the whole image as one reading region.
    """
    # Import locally to avoid a module cycle with the extraction entrypoint.
    try:
        from model.extract import preprocess_image, run
    except ModuleNotFoundError:
        from extract import preprocess_image, run

    with Image.open(path) as opened, tempfile.TemporaryDirectory(prefix="isd_layout_ocr_") as temp:
        source = ImageOps.exif_transpose(opened)
        if source.width * source.height > 30_000_000:
            raise ValueError("Image exceeds 30 million pixels")
        image = preprocess_image(source, mode)
        work = Path(temp)
        full = work / "full.png"
        image.save(full)
        lang = "eng" if language == "en" else "tha+eng"
        tsv = run("tesseract", full.name, "stdout", "-l", lang, "--psm", "4", "tsv", cwd=work)
        starts = _column_starts(_code_boxes(tsv))
        if not starts:
            return run("tesseract", full.name, "stdout", "-l", lang, "--psm", "4", cwd=work)

        code_boxes = _code_boxes(tsv)
        code_width = statistics.median(box.width for box in code_boxes)
        chunks = []
        for index, start in enumerate(starts):
            # The left edge is found from the aligned code glyphs. The right
            # edge is the next discovered code column, or the image edge.
            left = max(0, start - round(code_width / 2))
            right = starts[index + 1] if index + 1 < len(starts) else image.width
            if right - left < 100:
                continue
            aligned = [box for box in code_boxes if abs(box.left - start) <= code_width * 2]
            if not aligned:
                continue
            line_height = statistics.median(box.height for box in aligned)
            top = max(0, min(box.top for box in aligned) - round(line_height * 4))
            bottom = min(image.height, max(box.top + box.height for box in aligned) + round(line_height * 4))
            target = work / f"column-{index}.png"
            image.crop((left, top, right, bottom)).save(target)
            chunks.append(run("tesseract", target.name, "stdout", "-l", lang, "--psm", "6", cwd=work))
        body = "\n".join(chunks) if chunks else run("tesseract", full.name, "stdout", "-l", lang, "--psm", "4", cwd=work)
        lines = []
        for line in body.splitlines():
            # Table rules sometimes appear immediately before a course code.
            line = re.sub(r"^[+|!\s]+(?=\d{8}(?!\d))", "", line)
            line = re.sub(r"^1(?=\d{8}(?!\d))", "", line)
            lines.append(line)
        return "\n".join(lines)
