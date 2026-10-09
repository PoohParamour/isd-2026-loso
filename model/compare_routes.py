"""Compare embedded-text hybrid and Tesseract-only routes on the same PDFs."""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

from evaluate import evaluate_one
from extract import ROOT, extract


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-group", type=int, default=2)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads((ROOT / "model/data/manifest.json").read_text(encoding="utf-8"))
    selected = []
    for group in ("bachelor", "graduate"):
        for language in ("th", "en"):
            docs = sorted(
                (doc for doc in manifest["documents"] if doc["split"] == "dev" and doc["group"] == group and doc["language"] == language),
                key=lambda doc: doc["id"],
            )
            selected.extend(docs[: args.per_group])
    rows = []
    for doc in selected:
        gt = json.loads((ROOT / doc["gt"]).read_text(encoding="utf-8"))
        for route, force in (("hybrid", False), ("tesseract_only", True)):
            result = extract(ROOT / doc["pdf"], force_ocr=force)
            score = evaluate_one(result["record"], gt)
            correct = sum(bucket["correct"] for bucket in score["categories"].values())
            total = sum(bucket["total"] for bucket in score["categories"].values())
            rows.append({
                "id": doc["id"], "group": doc["group"], "language": doc["language"],
                "route": route, "engine": result["engine"], "seconds": result["processing_seconds"],
                "correct": correct, "total": total, "accuracy": correct / total,
            })
            print(doc["id"], route, result["processing_seconds"], f"{correct}/{total}", flush=True)
    matrix = {}
    for route in ("hybrid", "tesseract_only"):
        subset = [row for row in rows if row["route"] == route]
        matrix[route] = {
            "documents": len(subset),
            "correct": sum(row["correct"] for row in subset),
            "total": sum(row["total"] for row in subset),
            "accuracy": sum(row["correct"] for row in subset) / sum(row["total"] for row in subset),
            "mean_seconds": statistics.mean(row["seconds"] for row in subset),
            "max_seconds": max(row["seconds"] for row in subset),
            "api_cost_usd": 0,
        }
    report = {"split": "dev", "same_source_documents": len(selected), "matrix": matrix, "details": rows}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "details"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
