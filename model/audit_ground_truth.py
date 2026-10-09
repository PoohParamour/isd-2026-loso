"""Audit immutable labels against visible values from the source PDFs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from extract import ROOT, extract


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=("dev", "test"), default="test")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads((ROOT / "model/data/manifest.json").read_text(encoding="utf-8"))
    images = {path.stem: path for path in (ROOT / "all/Lab5_transcript_dataset/images/original").rglob("*.png")}
    rows = []
    for document in manifest["documents"]:
        if document["split"] != args.split or not document.get("gt"):
            continue
        truth = json.loads((ROOT / document["gt"]).read_text(encoding="utf-8"))
        visible = extract(ROOT / document["pdf"])["record"]
        image_record = extract(images[document["id"]])["record"]
        expected = truth.get("footer_detail", {}).get("updated_at")
        observed = visible.get("footer_detail", {}).get("updated_at")
        image_value = image_record.get("footer_detail", {}).get("updated_at")
        rows.append({
            "id": document["id"],
            "field": "footer_detail.updated_at",
            "ground_truth": expected,
            "visible_pdf_text": observed,
            "image_ocr": image_value,
            "matches": expected == observed,
            "image_ocr_matches_visible": image_value == observed,
        })
    report = {
        "split": args.split,
        "documents": len(rows),
        "field": "footer_detail.updated_at",
        "mismatches": sum(not row["matches"] for row in rows),
        "mismatch_fields_recovered_from_image": sum(
            not row["matches"] and row["image_ocr_matches_visible"] for row in rows
        ),
        "note": "Source labels are immutable; mismatches are reported, not rewritten.",
        "details": rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
