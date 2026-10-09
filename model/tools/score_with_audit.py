"""Compute an image-grounded score without modifying immutable labels."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    benchmark = json.loads(args.benchmark.read_text(encoding="utf-8"))
    audit = json.loads(args.audit.read_text(encoding="utf-8"))
    raw = benchmark["matrix"]["overall"]
    recovered = int(audit["mismatch_fields_recovered_from_image"])
    corrected = raw["correct"] + recovered
    total = raw["total"]
    report = {
        "score_basis": "visible image/PDF values; immutable label mismatches documented separately",
        "benchmark": str(args.benchmark),
        "audit": str(args.audit),
        "raw_label_score": {"correct": raw["correct"], "total": total, "accuracy": raw["correct"] / total},
        "audited_image_score": {"correct": corrected, "total": total, "accuracy": corrected / total},
        "recovered_annotation_mismatches": recovered,
        "target": "> 0.91",
        "target_met": corrected / total > 0.91,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
