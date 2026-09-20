"""Measure deployed API latency for a balanced batch, including comparison."""

from __future__ import annotations

import argparse
import json
import statistics
import time
import urllib.request
from pathlib import Path

from evaluate import evaluate_one
from extract import ROOT


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:3000/api/proxy/transcripts/extract")
    parser.add_argument("--split", choices=("dev", "test"), default="dev")
    parser.add_argument("--per-group", type=int, default=3)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads((ROOT / "model/data/manifest.json").read_text(encoding="utf-8"))
    selected = []
    for group in ("bachelor", "graduate"):
        for language in ("th", "en"):
            docs = sorted(
                (doc for doc in manifest["documents"] if doc["split"] == args.split and doc["group"] == group and doc["language"] == language),
                key=lambda doc: doc["id"],
            )
            selected.extend(docs[: args.per_group])
    if len(selected) != 4 * args.per_group:
        raise ValueError("Not enough documents for balanced batch")

    results = []
    batch_start = time.monotonic()
    for document in selected:
        pdf = ROOT / document["pdf"]
        boundary = "isdocrboundary"
        body = (
            ("--" + boundary + "\r\nContent-Disposition: form-data; name=\"file\"; filename=\"" + pdf.name + "\"\r\n"
             "Content-Type: application/pdf\r\n\r\n").encode()
            + pdf.read_bytes()
            + ("\r\n--" + boundary + "--\r\n").encode()
        )
        request = urllib.request.Request(
            args.url,
            data=body,
            headers={"Content-Type": "multipart/form-data; boundary=" + boundary},
            method="POST",
        )
        start = time.monotonic()
        with urllib.request.urlopen(request, timeout=120) as response:
            prediction = json.load(response)["record"]
        reference = json.loads((ROOT / document["gt"]).read_text(encoding="utf-8"))
        score = evaluate_one(prediction, reference)
        correct = sum(values["correct"] for values in score["categories"].values())
        total = sum(values["total"] for values in score["categories"].values())
        results.append({
            "id": document["id"],
            "group": document["group"],
            "language": document["language"],
            "seconds_with_comparison": round(time.monotonic() - start, 3),
            "correct": correct,
            "total": total,
        })
        print(document["id"], results[-1]["seconds_with_comparison"], f"{correct}/{total}", flush=True)
    durations = [row["seconds_with_comparison"] for row in results]
    report = {
        "route": args.url,
        "split": args.split,
        "batch_size": len(results),
        "batch_total_seconds": round(time.monotonic() - batch_start, 3),
        "mean_seconds_per_document": round(statistics.mean(durations), 3),
        "median_seconds_per_document": round(statistics.median(durations), 3),
        "max_seconds_per_document": max(durations),
        "bonus_latency_target_met": statistics.mean(durations) < 30,
        "exact_field_accuracy": sum(row["correct"] for row in results) / sum(row["total"] for row in results),
        "documents": results,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "documents"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
