"""Read-only experiment: filter noisy images before the current pipeline."""

import json
import tempfile
from pathlib import Path

from PIL import Image, ImageFilter

from model.evaluate import evaluate_one
from model.extract import extract

root = Path(__file__).resolve().parents[1]
manifest = json.loads((root / "model/data/manifest.json").read_text(encoding="utf-8"))
docs = {doc["id"]: doc for doc in manifest["documents"]}
base = root / "all/Lab5_transcript_dataset/images/augmented"
selected = ("71010009", "73036003", "74126003")
output = []
for doc_id in selected:
    doc = docs[doc_id]
    image_path = next(base.rglob(f"{doc_id}_aug2_noise.png"))
    truth = json.loads((root / doc["gt"]).read_text(encoding="utf-8"))
    with Image.open(image_path) as image, tempfile.TemporaryDirectory(prefix="noise_probe_") as temp:
        for name, filtered in (
            ("median3", image.filter(ImageFilter.MedianFilter(3))),
            ("gaussian05", image.filter(ImageFilter.GaussianBlur(0.5))),
        ):
            target = Path(temp) / f"{doc_id}_{name}.png"
            filtered.save(target)
            result = extract(target)
            score = evaluate_one(result["record"], truth)
            correct = sum(v["correct"] for v in score["categories"].values())
            total = sum(v["total"] for v in score["categories"].values())
            row = {"id": doc_id, "filter": name, "correct": correct,
                   "total": total, "rows": score["rows"],
                   "seconds": result["processing_seconds"]}
            output.append(row)
            print(json.dumps(row), flush=True)
(root / "tmp/noise-filter-probe.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
