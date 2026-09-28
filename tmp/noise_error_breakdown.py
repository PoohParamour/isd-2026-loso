"""Compare error categories for the largest paired noise regressions."""

import json
from pathlib import Path

from model.evaluate import evaluate_one
from model.extract import extract

root = Path(__file__).resolve().parents[1]
comparison = json.loads((root / "tmp/original-noise-comparison.json").read_text(encoding="utf-8"))
manifest = json.loads((root / "model/data/manifest.json").read_text(encoding="utf-8"))
docs = {doc["id"]: doc for doc in manifest["documents"]}
output = []
for entry in comparison:
    if entry["id"] not in {"71010009", "73036003", "73036011", "74126003"}:
        continue
    doc = docs[entry["id"]]
    image = next((root / "all/Lab5_transcript_dataset/images/augmented").rglob(f"{doc['id']}_aug2_noise.png"))
    truth = json.loads((root / doc["gt"]).read_text(encoding="utf-8"))
    score = evaluate_one(extract(image)["record"], truth)
    categories = {}
    for category in ("header", "course", "semester", "summary", "footer"):
        original = entry["original"]["categories"].get(category, {})
        noisy = score["categories"].get(category, {})
        categories[category] = {
            "original": f"{original.get('correct', 0)}/{original.get('total', 0)}",
            "noise": f"{noisy.get('correct', 0)}/{noisy.get('total', 0)}",
        }
    output.append({"id": doc["id"], "categories": categories})
    print(json.dumps(output[-1], ensure_ascii=False), flush=True)
(root / "tmp/noise-error-breakdown.json").write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
