"""Evaluate images while withholding each document from the course catalog.

This measures catalog generalization, not a new blind OCR test: parser and OCR
settings may already have been tuned on the development split.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from model import extract as extractor
from model.course_catalog import apply_course_catalog
from model.evaluate import evaluate_one
from model.tools.train_course_catalog import build_catalog

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", choices=("original", "aug2_noise"), required=True)
    parser.add_argument("--per-group", type=int, default=3)
    parser.add_argument("--all-dev", action="store_true", help="Evaluate every labeled dev source document")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    manifest = json.loads((ROOT / "model/data/manifest.json").read_text(encoding="utf-8"))
    selected = []
    if args.all_dev:
        selected = sorted((doc for doc in manifest["documents"]
                           if doc["split"] == "dev" and doc.get("gt")), key=lambda doc: doc["id"])
    else:
        for group in ("bachelor", "graduate"):
            for language in ("th", "en"):
                documents = sorted(
                    (doc for doc in manifest["documents"]
                     if doc["split"] == "dev" and doc["group"] == group and doc["language"] == language),
                    key=lambda doc: doc["id"],
                )
                selected.extend(documents[:args.per_group])
    if not selected or (not args.all_dev and len(selected) != 4 * args.per_group):
        raise ValueError("Not enough development documents")

    root = ROOT / "all/Lab5_transcript_dataset/images"
    image_root = root / ("original" if args.input == "original" else "augmented")
    original_apply = extractor.apply_course_catalog
    details = []
    try:
        for doc in selected:
            filename = doc["id"] + (".png" if args.input == "original" else "_aug2_noise.png")
            matches = list(image_root.rglob(filename))
            if len(matches) != 1:
                raise ValueError(f"Expected one image for {doc['id']}: {len(matches)} found")
            catalog = build_catalog(manifest, exclude_ids=frozenset({doc["id"]}))
            if catalog["source_documents"] != sum(
                item["split"] == "dev" and bool(item.get("gt")) for item in manifest["documents"]
            ) - 1:
                raise AssertionError("Held-out document was not excluded from catalog")
            extractor.apply_course_catalog = lambda record: apply_course_catalog(record, catalog)
            result = extractor.extract(matches[0])
            truth = json.loads((ROOT / doc["gt"]).read_text(encoding="utf-8"))
            score = evaluate_one(result["record"], truth)
            correct = sum(bucket["correct"] for bucket in score["categories"].values())
            total = sum(bucket["total"] for bucket in score["categories"].values())
            row = {
                "id": doc["id"], "group": doc["group"], "language": doc["language"],
                "correct": correct, "total": total, "rows": score["rows"],
                "seconds": result["processing_seconds"],
            }
            details.append(row)
            print(f"{doc['id']} {correct}/{total}", flush=True)
    finally:
        extractor.apply_course_catalog = original_apply

    correct = sum(row["correct"] for row in details)
    total = sum(row["total"] for row in details)
    tp = sum(row["rows"]["tp"] for row in details)
    fn = sum(row["rows"]["fn"] for row in details)
    fp = sum(row["rows"]["fp"] for row in details)
    report = {
        "input": args.input,
        "split": "dev",
        "evaluation": "document-held-out catalog; OCR/parser still tuned on dev",
        "documents": len(details),
        "correct": correct, "total": total, "exact_field_accuracy": correct / total,
        "rows": {"tp": tp, "fn": fn, "fp": fp,
                 "f1": 2 * tp / (2 * tp + fn + fp) if 2 * tp + fn + fp else 0},
        "mean_seconds": sum(row["seconds"] for row in details) / len(details),
        "details": details,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "details"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
