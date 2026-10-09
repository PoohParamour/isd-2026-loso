"""Evaluate original raster images, keeping them separate from PDF scores."""

from __future__ import annotations

import argparse
import collections
import json
import re
import statistics
from pathlib import Path

from evaluate import evaluate_one, flatten, norm
from extract import ROOT, extract


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=("dev", "test"), default="dev")
    parser.add_argument("--per-group", type=int, default=3)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads((ROOT / "model/data/manifest.json").read_text(encoding="utf-8"))
    images = {path.stem: path for path in (ROOT / "all/Lab5_transcript_dataset/images/original").rglob("*.png")}
    docs = []
    for group in ("bachelor", "graduate"):
        for language in ("th", "en"):
            group_docs = sorted(
                (doc for doc in manifest["documents"] if doc["split"] == args.split and doc["group"] == group and doc["language"] == language),
                key=lambda doc: doc["id"],
            )
            docs.extend(group_docs[: args.per_group])
    if len(docs) != 4 * args.per_group:
        raise ValueError("Not enough documents")

    rows = []
    matrix = collections.defaultdict(lambda: {"correct": 0, "total": 0, "tp": 0, "fn": 0, "fp": 0})
    field_errors = collections.Counter()
    examples = collections.defaultdict(list)
    for doc in docs:
        image = images.get(doc["id"])
        if not image:
            raise FileNotFoundError(doc["id"])
        result = extract(image)
        gt = json.loads((ROOT / doc["gt"]).read_text(encoding="utf-8"))
        score = evaluate_one(result["record"], gt)
        reference_fields = flatten(gt)
        predicted_fields = flatten(result["record"])
        for field, reference in reference_fields.items():
            expected = norm(reference, field)
            actual = norm(predicted_fields.get(field), field)
            if expected and expected != actual:
                # Collapse array indices so recurring field types are visible.
                field_type = re.sub(r"\[\d+\]", "[]", field)
                field_errors[field_type] += 1
                if len(examples[field_type]) < 3:
                    examples[field_type].append({"id": doc["id"], "expected": expected, "actual": actual})
        correct = sum(values["correct"] for values in score["categories"].values())
        total = sum(values["total"] for values in score["categories"].values())
        for label in ("overall", doc["group"] + "_" + doc["language"]):
            matrix[label]["correct"] += correct
            matrix[label]["total"] += total
            for key in ("tp", "fn", "fp"):
                matrix[label][key] += score["rows"][key]
        row = {
            "id": doc["id"],
            "group": doc["group"],
            "language": doc["language"],
            "predicted_format": result["record"]["format_id"],
            "seconds": result["processing_seconds"],
            "correct": correct,
            "total": total,
            "accuracy": correct / total,
        }
        rows.append(row)
        print(doc["id"], row["predicted_format"], f"{correct}/{total}", result["processing_seconds"], flush=True)
    for values in matrix.values():
        values["accuracy"] = values["correct"] / values["total"]
        precision = values["tp"] / (values["tp"] + values["fp"]) if values["tp"] + values["fp"] else 0
        recall = values["tp"] / (values["tp"] + values["fn"]) if values["tp"] + values["fn"] else 0
        values["row_f1"] = 2 * precision * recall / (precision + recall) if precision + recall else 0
    report = {
        "input": "Lab5 original PNG, 150 DPI",
        "split": args.split,
        "documents": len(rows),
        "mean_seconds": statistics.mean(row["seconds"] for row in rows),
        "matrix": dict(matrix),
        "top_field_errors": [
            {"field": field, "errors": count, "examples": examples[field]}
            for field, count in field_errors.most_common()
        ],
        "details": rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "details"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
