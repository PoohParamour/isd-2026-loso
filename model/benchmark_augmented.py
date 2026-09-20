"""Evaluate augmented transcript images separately by noise type and format."""

from __future__ import annotations

import argparse
import collections
import json
import statistics
from pathlib import Path

from evaluate import evaluate_one
from extract import ROOT, extract


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=("dev", "test"), default="dev")
    parser.add_argument("--per-group", type=int, default=3)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads((ROOT / "model/data/manifest.json").read_text(encoding="utf-8"))
    image_root = ROOT / "all/Lab5_transcript_dataset/images/augmented"
    images = collections.defaultdict(list)
    for image in image_root.rglob("*.png"):
        document_id = image.stem.split("_aug", 1)[0]
        images[document_id].append(image)

    selected = []
    for group in ("bachelor", "graduate"):
        for language in ("th", "en"):
            documents = sorted(
                (doc for doc in manifest["documents"] if doc["split"] == args.split and doc["group"] == group and doc["language"] == language),
                key=lambda doc: doc["id"],
            )
            selected.extend(documents[: args.per_group])

    rows = []
    buckets = collections.defaultdict(lambda: {"correct": 0, "total": 0, "tp": 0, "fn": 0, "fp": 0, "seconds": []})
    for doc in selected:
        truth = json.loads((ROOT / doc["gt"]).read_text(encoding="utf-8"))
        for image in sorted(images[doc["id"]]):
            augmentation = image.stem.split("_", 1)[1]
            result = extract(image)
            score = evaluate_one(result["record"], truth)
            correct = sum(values["correct"] for values in score["categories"].values())
            total = sum(values["total"] for values in score["categories"].values())
            row = {
                "id": doc["id"], "group": doc["group"], "language": doc["language"],
                "augmentation": augmentation, "predicted_format": result["record"]["format_id"],
                "seconds": result["processing_seconds"], "correct": correct, "total": total,
                "accuracy": correct / total,
            }
            rows.append(row)
            for label in ("overall", augmentation, f"{doc['group']}_{doc['language']}", f"{doc['group']}_{doc['language']}__{augmentation}"):
                bucket = buckets[label]
                bucket["correct"] += correct
                bucket["total"] += total
                bucket["seconds"].append(result["processing_seconds"])
                for key in ("tp", "fn", "fp"):
                    bucket[key] += score["rows"][key]
            print(doc["id"], augmentation, f"{correct}/{total}", result["processing_seconds"], flush=True)

    matrix = {}
    for label, bucket in buckets.items():
        precision = bucket["tp"] / (bucket["tp"] + bucket["fp"]) if bucket["tp"] + bucket["fp"] else 0
        recall = bucket["tp"] / (bucket["tp"] + bucket["fn"]) if bucket["tp"] + bucket["fn"] else 0
        matrix[label] = {
            "documents": len(bucket["seconds"]), "correct": bucket["correct"], "total": bucket["total"],
            "accuracy": bucket["correct"] / bucket["total"],
            "row_f1": 2 * precision * recall / (precision + recall) if precision + recall else 0,
            "mean_seconds": statistics.mean(bucket["seconds"]), "max_seconds": max(bucket["seconds"]),
        }
    report = {"input": "Lab5 augmented PNG", "split": args.split, "documents": len(rows), "matrix": matrix, "details": rows}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"overall": matrix.get("overall")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
