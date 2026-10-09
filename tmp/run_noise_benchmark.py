"""Benchmark the main model on aug2_noise PNGs from the dev split."""

import argparse
import json
from pathlib import Path

from model.evaluate import evaluate_one
from model.extract import extract


parser = argparse.ArgumentParser()
parser.add_argument("--split", choices=("dev", "test"), default="dev")
parser.add_argument("--out", type=Path)
parser.add_argument("--image-layout", choices=("auto", "profile", "detected"), default="auto")
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
manifest = json.loads((root / "model/data/manifest.json").read_text(encoding="utf-8"))
image_root = root / "all/Lab5_transcript_dataset/images/augmented"
report_path = args.out or root / f"tmp/noise-benchmark-{args.split}-current.json"
selected = []
for group in ("bachelor", "graduate"):
    for language in ("th", "en"):
        docs = sorted(
            (doc for doc in manifest["documents"]
             if doc["split"] == args.split and doc["group"] == group and doc["language"] == language),
            key=lambda doc: doc["id"],
        )
        selected.extend(docs[:3])

rows = []
for doc in selected:
    paths = list(image_root.rglob(f"{doc['id']}_aug2_noise.png"))
    if len(paths) != 1:
        raise RuntimeError(f"Expected one noise image for {doc['id']}; found {len(paths)}")
    result = extract(paths[0], image_layout=args.image_layout)
    truth = json.loads((root / doc["gt"]).read_text(encoding="utf-8"))
    score = evaluate_one(result["record"], truth)
    correct = sum(v["correct"] for v in score["categories"].values())
    total = sum(v["total"] for v in score["categories"].values())
    row = {
        "id": doc["id"], "group": doc["group"], "language": doc["language"],
        "correct": correct, "total": total,
        "accuracy": correct / total if total else 0,
        "rows": score["rows"], "seconds": result["processing_seconds"],
        "predicted_format": result["record"].get("format_id"),
    }
    rows.append(row)
    report_path.write_text(json.dumps({"split": args.split, "augmentation": "aug2_noise", "details": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(row, ensure_ascii=False), flush=True)

correct = sum(row["correct"] for row in rows)
total = sum(row["total"] for row in rows)
tp = sum(row["rows"]["tp"] for row in rows)
fn = sum(row["rows"]["fn"] for row in rows)
fp = sum(row["rows"]["fp"] for row in rows)
report = {
    "split": args.split, "augmentation": "aug2_noise", "image_layout": args.image_layout, "documents": len(rows),
    "correct": correct, "total": total,
    "exact_field_accuracy": correct / total,
    "rows": {"tp": tp, "fn": fn, "fp": fp,
             "f1": 2 * tp / (2 * tp + fn + fp) if 2 * tp + fn + fp else 0},
    "mean_seconds": sum(row["seconds"] for row in rows) / len(rows),
    "details": rows,
}
report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({k: v for k, v in report.items() if k != "details"}, ensure_ascii=False), flush=True)
