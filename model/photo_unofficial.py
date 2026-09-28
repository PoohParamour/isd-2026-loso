"""Read a rectified, high-resolution unofficial English transcript photo.

This route uses page geometry only. It never reads a matching PDF, filename,
or ground truth during inference.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps


MODEL_DIR = Path(__file__).resolve().parent / "data/photo_ocr"


def _table_top(image: Image.Image) -> int | None:
    gray = np.asarray(image.convert("L"))
    height, width = gray.shape
    binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    joined = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, np.ones((1, 9), np.uint8))
    horizontal = cv2.morphologyEx(
        joined, cv2.MORPH_OPEN, np.ones((1, max(25, round(width * 0.12))), np.uint8)
    )
    counts = (horizontal > 0).sum(axis=1)
    rows = np.flatnonzero(
        (counts > width * 0.4)
        & (np.arange(height) > height * 0.08)
        & (np.arange(height) < height * 0.5)
    )
    return int(rows[0]) if len(rows) else None


def read_unofficial_photo(path: Path) -> tuple[str, str] | None:
    """Return header/footer OCR and isolated table OCR when geometry is clear."""
    if not (MODEL_DIR / "eng_photo.traineddata").exists():
        return None
    with Image.open(path) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGB")
    width, height = image.size
    # Below this size, photographed glyphs are only a few pixels tall. Keep
    # the established review path instead of promoting a noisy second pass.
    if width < 900 or height <= width:
        return None
    top = _table_top(image)
    if top is None:
        return None
    try:
        from model.extract import run
    except ModuleNotFoundError:
        from extract import run

    body = image.crop((0, max(0, top - round(height * 0.01)),
                       round(width * 0.58), round(height * 0.92)))
    body = body.resize((body.width * 2, body.height * 2), Image.Resampling.LANCZOS)
    body = ImageOps.autocontrast(body.convert("L"))
    header = image.crop((0, 0, width, round(height * 0.22)))
    footer = image.crop((0, round(height * 0.79), width, height))
    with tempfile.TemporaryDirectory(prefix="isd_unofficial_") as temp:
        work = Path(temp)

        def ocr(region: Image.Image, name: str, psm: int) -> str:
            target = work / f"{name}.png"
            region.save(target)
            return run("tesseract", target.name, "stdout", "-l", "eng_photo",
                       "--tessdata-dir", str(MODEL_DIR), "--psm", str(psm), cwd=work)

        header_text = ocr(header.resize((header.width * 2, header.height * 2)), "header", 6)
        footer_text = ocr(footer.resize((footer.width * 2, footer.height * 2)), "footer", 6)
        body_text = ocr(body, "table", 4)
    return "\n".join((header_text, footer_text, body_text)), body_text
