"""Line-level OCR for a rectified ruled English transcript photograph.

Geometry and visible ink determine every row; labels and reference PDFs are
never loaded. The recognizer can be selected for benchmark/checkpoint trials.
"""

from __future__ import annotations

import re
import tempfile
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps


def line_bands(ink: np.ndarray, min_pixels: int) -> list[tuple[int, int]]:
    rows = np.flatnonzero((ink > 0).sum(axis=1) >= min_pixels)
    groups = np.split(rows, np.flatnonzero(np.diff(rows) > 3) + 1)
    return [(int(g[0]), int(g[-1]) + 1) for g in groups if len(g) >= 3]


def plausible_gpa_line(text: str) -> bool:
    values = re.findall(r"\d+\.\d{2}", text)
    if not values or any(not 0 <= float(value) <= 4 for value in values):
        return False
    if re.search(r"Cumulative\s+GPA", text, re.IGNORECASE):
        return True
    if re.search(r"GPS\s*:", text, re.IGNORECASE):
        return len(values) >= 2 or bool(re.search(r"GPS\s*:\s*-", text, re.IGNORECASE))
    return False


def ruled_geometry(
    gray: np.ndarray,
) -> tuple[int, list[tuple[int, int, int, int]], np.ndarray] | None:
    """Detect long table rules with a bounded search over their shear angle."""
    h, w = gray.shape
    if w > 1600:
        factor = w / 1600
        small = cv2.resize(
            gray, (1600, round(h / factor)), interpolation=cv2.INTER_AREA
        )
        result = ruled_geometry(small)
        if result is None:
            return None
        top, columns, mask = result
        return (
            round(top * factor),
            [tuple(round(x * factor) for x in col) for col in columns],
            cv2.resize(mask, (w, h), interpolation=cv2.INTER_NEAREST),
        )
    normalized = cv2.divide(gray, cv2.GaussianBlur(gray, (0, 0), 8), scale=255)
    binary = cv2.threshold(normalized, 180, 255, cv2.THRESH_BINARY_INV)[1]
    peaks = np.zeros(w)
    slopes = np.zeros(w)
    horizontal = np.zeros(h)
    for slope in np.linspace(-0.03, 0.03, 31):
        shear = cv2.warpAffine(
            binary,
            np.float32([[1, -slope, slope * h / 2], [0, 1, 0]]),
            (w, h),
            flags=cv2.INTER_NEAREST,
        )
        counts = (shear[round(h * 0.22) : round(h * 0.88)] > 0).sum(axis=0)
        slopes[counts > peaks] = slope
        peaks = np.maximum(peaks, counts)
        shear = cv2.warpAffine(
            binary,
            np.float32([[1, 0, 0], [-slope, 1, slope * w / 2]]),
            (w, h),
            flags=cv2.INTER_NEAREST,
        )
        horizontal = np.maximum(
            horizontal, (shear[:, round(w * 0.025) : round(w * 0.975)] > 0).sum(axis=1)
        )
    rows = np.flatnonzero(
        (horizontal > w * 0.6) & (np.arange(h) > h * 0.08) & (np.arange(h) < h * 0.5)
    )
    if not len(rows):
        return None
    top = int(rows[0])
    xs = np.flatnonzero(peaks > h * 0.4)
    groups = np.split(xs, np.flatnonzero(np.diff(xs) > w * 0.012) + 1)
    borders = [int(g[np.argmax(peaks[g])]) for g in groups if len(g)]
    lines = [(x, float(slopes[x])) for x in borders]
    columns = []
    for a, b, c in zip(borders, borders[1:], borders[2:]):
        if (
            0.025 * w < b - a < 0.065 * w
            and 0.025 * w < c - b < 0.065 * w
            and 0.65 < (b - a) / (c - b) < 1.5
        ):
            lefts = [x for x in borders if w * 0.02 < x < a - w * 0.25]
            if lefts:
                # Only outer rules can be the title's left boundary.
                eligible = lefts if a < w * 0.65 else [x for x in lefts if x > w * 0.35]
                if not eligible:
                    continue
                left = min(eligible) if a < w * 0.65 else max(eligible)
                columns.append((left, a, b, c))
    if not columns or not any(w * 0.3 < a < w * 0.65 for _, a, _, _ in columns):
        return None
    mask = np.zeros_like(gray)
    for mid, slope in lines:
        cv2.line(
            mask,
            (round(mid + slope * (top - h * 0.5)), top),
            (round(mid + slope * (h - h * 0.5)), h),
            255,
            5,
        )
    return top, columns, mask


def read_phone_table(
    path: Path, model_dir: Path | None = None, language: str = "eng"
) -> tuple[str, str] | None:
    try:
        from model.extract import parse_term, run
    except ModuleNotFoundError:
        from extract import parse_term, run

    with Image.open(path) as opened:
        image = ImageOps.exif_transpose(opened).convert("L")
    if image.width < 900 or image.height <= image.width:
        return None
    if image.width > 2200:
        image = image.resize(
            (2200, round(image.height * 2200 / image.width)), Image.Resampling.LANCZOS
        )
    gray = np.asarray(image)
    height, width = gray.shape
    geometry = ruled_geometry(gray)
    if geometry is None:
        return None
    top, columns, rule_mask = geometry
    norm = cv2.divide(gray, cv2.GaussianBlur(gray, (0, 0), 8), scale=255)
    binary = cv2.threshold(norm, 170, 255, cv2.THRESH_BINARY_INV)[1]
    vertical = cv2.morphologyEx(
        binary, cv2.MORPH_OPEN, np.ones((height // 3, 1), np.uint8)
    )
    horizontal = cv2.morphologyEx(
        binary, cv2.MORPH_OPEN, np.ones((1, max(50, round(width * 0.12))), np.uint8)
    )
    rules = cv2.dilate(vertical | horizontal | rule_mask, np.ones((3, 3), np.uint8))
    cleaned = norm.copy()
    cleaned[rules > 0] = 255
    stripped = cv2.threshold(cleaned, 170, 255, cv2.THRESH_BINARY_INV)[1]
    with tempfile.TemporaryDirectory(prefix="isd_phone_rows_") as temp:
        work = Path(temp)
        serial = 0

        def ocr(box, psm=7, digits=False, use_model=True):
            nonlocal serial
            l, t, r, b = map(int, box)
            l, t, r, b = max(0, l), max(0, t), min(width, r), min(height, b)
            if b <= t or r <= l:
                return ""
            crop = Image.fromarray(cleaned[t:b, l:r])
            scale = max(1, 32 / crop.height)
            crop = crop.resize(
                (round(crop.width * scale), round(crop.height * scale)),
                Image.Resampling.LANCZOS,
            )
            crop = ImageOps.expand(crop, 8, "white")
            target = work / f"line{serial}.png"
            serial += 1
            crop.save(target)
            args = [
                "tesseract",
                str(target),
                "stdout",
                "--oem",
                "1",
                "-l",
                language if use_model else "eng",
                "--psm",
                str(psm),
            ]
            if model_dir is not None and use_model:
                args += ["--tessdata-dir", str(model_dir)]
            if digits:
                args += ["-c", "tessedit_char_whitelist=0123456789"]
            return run(*args).strip()

        initial_header = ocr((0, 0, width, top - 3), 6, use_model=False)
        if not re.search(r"Unofficial\s+Transcript", initial_header, re.IGNORECASE):
            return None
        middle = round((columns[0][1] + columns[0][2]) * 0.5)
        header_lines = []
        header_left = max(0, columns[0][0] - round(width * 0.01))
        header_right = round(width * 0.82)
        header_bands = line_bands(
            stripped[round(top * 0.4) : top - 4, header_left:middle],
            max(5, round(width * 0.003)),
        )
        for lo, hi in header_bands:
            lo += round(top * 0.4)
            hi += round(top * 0.4)
            pad = max(3, round((hi - lo) * 0.2))
            whole = ocr(
                (header_left, lo - pad, header_right, hi + pad), use_model=False
            )
            if re.match(r"\s*Program", whole, re.IGNORECASE):
                header_lines.append(
                    ocr((header_left, lo - pad, header_right, hi + pad))
                )
            else:
                header_lines.extend(
                    (
                        ocr((header_left, lo - pad, middle, hi + pad)),
                        ocr(
                            (middle, lo - pad, header_right, hi + pad), use_model=False
                        ),
                    )
                )
        header = "Unofficial Transcript\n" + "\n".join(
            line.strip(" |") for line in header_lines
        )
        header = re.sub(
            r"\bStudent\s+[I1l]D\b", "Student ID", header, flags=re.IGNORECASE
        )
        body = []
        footer = []
        for start, title_end, credit_end, grade_end in columns:
            # Projection on the wide title cell gives the baseline of each
            # printed line, including headings, continuations, and summaries.
            left = max(0, start - round(width * 0.01))
            right = title_end - 5
            bands = line_bands(
                stripped[top + 15 :, left:right], max(5, round((right - left) * 0.006))
            )
            for lo, hi in bands:
                lo += top + 15
                hi += top + 15
                if hi - lo < 5:
                    continue
                pad = max(3, round((hi - lo) * 0.2))
                text = ocr((left, lo - pad, right, hi + pad))
                if not text:
                    continue
                text = re.sub(r"^[|.:\s]+", "", text)
                is_course = re.match(r"^\d{7,9}\s", text)
                if not is_course:
                    generic = ocr((left, lo - pad, right, hi + pad), use_model=False)
                    # Headings, GPA rows and summaries use their independently
                    # recognized labels; no calendar values are inferred.
                    if (
                        parse_term(generic, "en")
                        or (
                            plausible_gpa_line(generic) and not plausible_gpa_line(text)
                        )
                        or re.search(
                            r"Total\s+(?:number|credit)", generic, re.IGNORECASE
                        )
                    ):
                        text = generic
                if re.search(
                    r"Total\s+(?:number|credit)|Cumulative|Transcript\s+Closed|Checked|Date\s+Issued",
                    text,
                    re.IGNORECASE,
                ):
                    footer.append(text)
                    continue
                if re.search(r"Semester|Sermester|GPS|GPA", text, re.IGNORECASE):
                    body.append(text)
                    continue
                code = re.match(r"^(\d{7,9})\s+(.+)", text)
                if code:
                    credit = ocr(
                        (title_end + 5, lo - pad, credit_end - 5, hi + pad), digits=True
                    )
                    grade = ocr((credit_end + 5, lo - pad, grade_end - 5, hi + pad))
                    grade = re.sub(r"\s+", "", grade).strip("|.,:")
                    credit = credit if re.fullmatch(r"\d{1,2}", credit) else "?"
                    grade = (
                        grade
                        if re.fullmatch(
                            r"[A-F][+]?|S|I|W|P|NP|U|G|-", grade, re.IGNORECASE
                        )
                        else "?"
                        if grade
                        else ""
                    )
                    body.append(f"{code[1]} {code[2]} {credit} {grade}".strip())
                else:
                    body.append(text)
        # Issue date lies outside the table; read the bottom portion separately.
        bottom = ocr((0, height * 0.8, width, height), 6, use_model=False)
        footer.extend(
            line
            for line in bottom.splitlines()
            if re.search(r"Total|Cumulative|Date Issued", line, re.IGNORECASE)
        )
    return "\n".join((header, *footer, *body)), "\n".join(body)
