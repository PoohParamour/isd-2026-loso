import json
from pathlib import Path

from model.evaluate import evaluate_one
from model.extract import extract

root = Path(__file__).resolve().parents[1]
manifest = json.loads((root / "model/data/manifest.json").read_text(encoding="utf-8"))
docs = {doc["id"]: doc for doc in manifest["documents"]}
for doc_id in ("71020005", "71030005", "73036003", "74126003"):
    doc = docs[doc_id]
    image = next((root / "all/Lab5_transcript_dataset/images/augmented").rglob(f"{doc_id}_aug2_noise.png"))
    record = extract(image)["record"]
    truth = json.loads((root / doc["gt"]).read_text(encoding="utf-8"))
    score = evaluate_one(record, truth)
    print(json.dumps({"id": doc_id, "correct": sum(v["correct"] for v in score["categories"].values()),
                      "total": sum(v["total"] for v in score["categories"].values()), "rows": score["rows"]}), flush=True)
