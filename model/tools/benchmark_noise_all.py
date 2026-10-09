"""Run every labeled bachelor and graduate grain-noise image through extraction."""

from __future__ import annotations

import collections
import json
from pathlib import Path

from model.evaluate import evaluate_one
from model.extract import ROOT, extract


IMAGE_ROOT = ROOT / "all/Lab5_transcript_dataset/images/augmented"
REPORT_PATH = ROOT / "model/reports/noise-all-20260925.json"


def summarize(rows: list[dict]) -> dict:
    correct = sum(row["correct"] for row in rows)
    total = sum(row["total"] for row in rows)
    tp = sum(row["rows"]["tp"] for row in rows)
    fn = sum(row["rows"]["fn"] for row in rows)
    fp = sum(row["rows"]["fp"] for row in rows)
    return {
        "documents": len(rows),
        "correct": correct,
        "total": total,
        "exact_field_accuracy_micro": correct / total if total else None,
        "exact_field_accuracy_macro": sum(row["accuracy"] for row in rows) / len(rows) if rows else None,
        "rows": {"tp": tp, "fn": fn, "fp": fp,
                 "f1": 2 * tp / (2 * tp + fn + fp) if 2 * tp + fn + fp else None},
        "mean_seconds": sum(row["seconds"] for row in rows) / len(rows) if rows else None,
    }


def main() -> None:
    manifest = json.loads((ROOT / "model/data/manifest.json").read_text(encoding="utf-8"))
    documents = sorted((doc for doc in manifest["documents"] if doc.get("gt")), key=lambda doc: doc["id"])
    images = collections.defaultdict(list)
    for image in IMAGE_ROOT.rglob("*_aug2_noise.png"):
        images[image.stem.split("_aug2_noise", 1)[0]].append(image)

    rows = []
    for doc in documents:
        matches = images[doc["id"]]
        if len(matches) != 1:
            raise ValueError(f"Expected one noise image for {doc['id']}, found {len(matches)}")
        result = extract(matches[0], image_layout="auto")
        truth = json.loads((ROOT / doc["gt"]).read_text(encoding="utf-8"))
        score = evaluate_one(result["record"], truth)
        correct = sum(bucket["correct"] for bucket in score["categories"].values())
        total = sum(bucket["total"] for bucket in score["categories"].values())
        row = {
            "id": doc["id"], "split": doc["split"], "group": doc["group"],
            "language": doc["language"], "image": str(matches[0].relative_to(ROOT)),
            "predicted_format": result["record"].get("format_id"),
            "correct": correct, "total": total, "accuracy": correct / total,
            "rows": score["rows"], "seconds": result["processing_seconds"],
        }
        rows.append(row)
        print(f"{len(rows)}/{len(documents)} {doc['id']} {correct}/{total}", flush=True)

    matrix = {"overall": summarize(rows)}
    for key in ("group", "language", "split"):
        for value in sorted({row[key] for row in rows}):
            matrix[f"{key}:{value}"] = summarize([row for row in rows if row[key] == value])
    for group in ("bachelor", "graduate"):
        for language in ("th", "en"):
            matrix[f"{group}_{language}"] = summarize(
                [row for row in rows if row["group"] == group and row["language"] == language]
            )
    report = {
        "input": "Existing Lab5 aug2_noise PNG images (Gaussian sensor grain, sigma 8-18)",
        "pipeline": "extract(image, image_layout='auto')",
        "metric": "Exact match on nonempty ground-truth fields; row F1 by semester, year, and course code",
        "note": "Existing dev/test documents have informed earlier OCR and parser tuning; this is a robustness check, not a blind generalization estimate.",
        "unlabeled_images_excluded": sorted(set(images) - {doc["id"] for doc in documents}),
        "matrix": matrix, "details": rows,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(matrix, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
