"""Compare current-model original images with saved noise results, same documents."""

import json
from pathlib import Path

from model.evaluate import evaluate_one
from model.extract import extract

root = Path(__file__).resolve().parents[1]
noise = json.loads((root / "tmp/noise-benchmark-current.json").read_text(encoding="utf-8"))
manifest = json.loads((root / "model/data/manifest.json").read_text(encoding="utf-8"))
docs = {item["id"]: item for item in manifest["documents"]}
report_path = root / "tmp/original-noise-comparison.json"
rows = []
for noisy in noise["details"]:
    doc = docs[noisy["id"]]
    image = root / f"all/Lab5_transcript_dataset/images/original/{'G' if doc['group'] == 'graduate' else 'th'}/{doc['id']}.png"
    truth = json.loads((root / doc["gt"]).read_text(encoding="utf-8"))
    result = extract(image)
    score = evaluate_one(result["record"], truth)
    correct = sum(v["correct"] for v in score["categories"].values())
    total = sum(v["total"] for v in score["categories"].values())
    row = {
        "id": doc["id"], "group": doc["group"], "language": doc["language"],
        "original": {"correct": correct, "total": total, "rows": score["rows"],
                     "categories": score["categories"]},
        "noise": {"correct": noisy["correct"], "total": noisy["total"],
                  "rows": noisy["rows"]},
    }
    rows.append(row)
    report_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"id": doc["id"], "original": f"{correct}/{total}",
                      "noise": f"{noisy['correct']}/{noisy['total']}",
                      "original_rows": score["rows"], "noise_rows": noisy["rows"]},
                     ensure_ascii=False), flush=True)
