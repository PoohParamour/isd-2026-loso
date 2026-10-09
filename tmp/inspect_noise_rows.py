"""Locate course rows lost by the current OCR path on selected noisy images."""

import json
import re
from pathlib import Path

from model.extract import detect_format, extract, read_document, read_image_profile

root = Path(__file__).resolve().parents[1]
manifest = json.loads((root / "model/data/manifest.json").read_text(encoding="utf-8"))
docs = {doc["id"]: doc for doc in manifest["documents"]}
for doc_id in ("71010009", "73036003", "74126003", "71020005"):
    doc = docs[doc_id]
    image = next((root / "all/Lab5_transcript_dataset/images/augmented").rglob(f"{doc_id}_aug2_noise.png"))
    truth = json.loads((root / doc["gt"]).read_text(encoding="utf-8"))
    initial, _ = read_document(image)
    fmt = detect_format(initial)
    full, body = read_image_profile(image, fmt)
    result = extract(image)["record"]
    gt_codes = {str(s["subject_id"]) for term in truth["transcript_detail"]["semesters"] for s in term["subject"]}
    pred_codes = {str(s["subject_id"]) for term in result["transcript_detail"]["semesters"] for s in term["subject"]}
    body_codes = set(re.findall(r"(?<!\d)\d{8}(?!\d)", body or ""))
    missing = sorted(gt_codes - pred_codes)
    report = {
        "id": doc_id, "format": fmt, "gt_count": len(gt_codes), "pred_count": len(pred_codes),
        "missing_codes": missing,
        "missing_visible_in_body_ocr": sorted(set(missing) & body_codes),
        "body_course_lines": [line for line in (body or "").splitlines() if re.search(r"\d{5,}|(?:Cr|Nc|Ad)\s+\d|Semester|ภาคการศึกษา", line, re.I)],
    }
    print(json.dumps(report, ensure_ascii=False), flush=True)
