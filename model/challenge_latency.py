"""Benchmark the bonus task: extract and compare a balanced batch."""

from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path

from evaluate import evaluate_one
from extract import ROOT, extract


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=ROOT / "model/data/manifest.json")
    parser.add_argument("--split", choices=("dev", "test"), default="dev")
    parser.add_argument("--per-group", type=int, default=3)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    selected = []
    for group in ("bachelor", "graduate"):
        for language in ("th", "en"):
            documents = sorted((d for d in manifest["documents"] if d["split"] == args.split and d["group"] == group and d["language"] == language), key=lambda d: d["id"])
            selected.extend(documents[: args.per_group])
    if len(selected) != 4 * args.per_group:
        raise ValueError("Not enough labeled documents for a balanced batch")

    rows = []
    batch_start = time.monotonic()
    for document in selected:
        start = time.monotonic()
        result = extract(ROOT / document["pdf"])
        # Ground truth is loaded only after extraction, for comparison.
        gt = json.loads((ROOT / document["gt"]).read_text(encoding="utf-8"))
        score = evaluate_one(result["record"], gt)
        correct = sum(x["correct"] for x in score["categories"].values())
        total = sum(x["total"] for x in score["categories"].values())
        rows.append({
            "id": document["id"], "group": document["group"], "language": document["language"],
            "engine": result["engine"], "seconds_with_comparison": round(time.monotonic() - start, 3),
            "correct": correct, "total": total, "accuracy": correct / total if total else 0,
        })
    batch_seconds = time.monotonic() - batch_start
    durations = sorted(x["seconds_with_comparison"] for x in rows)
    report = {
        "split": args.split,
        "batch_size": len(rows),
        "batch_total_seconds": round(batch_seconds, 3),
        "mean_seconds_per_document": round(statistics.mean(durations), 3),
        "median_seconds_per_document": round(statistics.median(durations), 3),
        "max_seconds_per_document": max(durations),
        "bonus_latency_target_met": statistics.mean(durations) < 30,
        "exact_field_accuracy": sum(x["correct"] for x in rows) / sum(x["total"] for x in rows),
        "documents": rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "documents"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
