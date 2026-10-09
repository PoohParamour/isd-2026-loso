"""Run extraction on a manifest split without reading labels."""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

from extract import ROOT, extract


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=ROOT / "model/data/manifest.json")
    parser.add_argument("--split", choices=("dev", "test"), default="dev")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--force-ocr", action="store_true")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    args.out.mkdir(parents=True, exist_ok=True)
    durations = []
    failures = []
    engines = {}
    for document in manifest["documents"]:
        if document["split"] != args.split:
            continue
        try:
            result = extract(ROOT / document["pdf"], force_ocr=args.force_ocr)
            (args.out / f"{document['id']}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            durations.append(result["processing_seconds"])
            engines[result["engine"]] = engines.get(result["engine"], 0) + 1
            print(document["id"], result["record"]["format_id"], result["engine"], result["processing_seconds"])
        except Exception as exc:
            failures.append({"id": document["id"], "error": str(exc)})
            print(document["id"], "FAILED", str(exc))
    summary = {
        "split": args.split,
        "documents": len(durations),
        "failures": failures,
        "engines": engines,
        "mean_seconds": statistics.mean(durations) if durations else None,
        "median_seconds": statistics.median(durations) if durations else None,
        "max_seconds": max(durations) if durations else None,
    }
    (args.out / "benchmark.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
