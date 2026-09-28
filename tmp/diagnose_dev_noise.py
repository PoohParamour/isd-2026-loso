"""Inspect dev-only noise errors; never imported by inference."""

import json
from pathlib import Path

from model.evaluate import flatten, norm, row_keys
from model.extract import extract

ROOT = Path(__file__).resolve().parents[1]
manifest = json.loads((ROOT / "model/data/manifest.json").read_text(encoding="utf-8"))
documents = {doc["id"]: doc for doc in manifest["documents"] if doc["split"] == "dev"}
for doc_id in ("71010009", "71010005", "73046003"):
    doc = documents[doc_id]
    image = next((ROOT / "all/Lab5_transcript_dataset/images/augmented").rglob(f"{doc_id}_aug2_noise.png"))
    prediction = extract(image)["record"]
    reference = json.loads((ROOT / doc["gt"]).read_text(encoding="utf-8"))
    expected = flatten(reference)
    actual = flatten(prediction)
    print(f"\n{doc_id}")
    print("missing rows:", row_keys(reference) - row_keys(prediction))
    print("extra rows:", row_keys(prediction) - row_keys(reference))
    for field, value in expected.items():
        left = norm(value, field)
        right = norm(actual.get(field), field)
        if left and left != right:
            print(f"{field}: {left[:50]!r} -> {right[:50]!r}")
