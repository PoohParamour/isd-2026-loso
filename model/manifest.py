"""Audit transcript inputs and create a reproducible, document-level split.

Only file names and schema metadata are written. Source PDFs and labels remain
untouched. Images derived from a PDF must inherit that PDF's split.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "model" / "data"
SEED = "isd-p1-2026-09-20-v1"
GROUPS = {
    "bachelor": ("input_Bachelor_Degrees", "ground_truth_Bachelor_Degrees"),
    "graduate": ("input_Master", "ground_truth_Master"),
}


def sort_key(item: dict) -> str:
    return hashlib.sha256(f"{SEED}:{item['id']}".encode()).hexdigest()


def build() -> dict:
    documents: list[dict] = []
    orphan_labels: list[str] = []
    for group, (input_dir, gt_dir) in GROUPS.items():
        pdf_dir = ROOT / "data_transcript" / input_dir
        label_dir = ROOT / "ground_truth_transcript" / gt_dir
        labels = {p.stem.split("_")[1]: p for p in label_dir.glob("*.json")}
        seen: set[str] = set()
        for pdf in sorted(pdf_dir.glob("*.pdf")):
            doc_id = pdf.stem
            gt_path = labels.get(doc_id)
            item = {
                "id": doc_id,
                "group": group,
                "pdf": str(pdf.relative_to(ROOT)),
                "gt": str(gt_path.relative_to(ROOT)) if gt_path else None,
                "language": gt_path.stem.rsplit("_", 1)[-1] if gt_path else None,
                "split": "unlabeled" if not gt_path else "dev",
            }
            if gt_path:
                seen.add(doc_id)
                label = json.loads(gt_path.read_text(encoding="utf-8"))
                embedded_id = str(label.get("header_detail", {}).get("student_id", ""))
                if embedded_id != doc_id:
                    raise ValueError(f"ID mismatch in {gt_path}: {embedded_id} != {doc_id}")
            documents.append(item)
        orphan_labels.extend(str(p.relative_to(ROOT)) for k, p in labels.items() if k not in seen)

    # Hold out three source documents per group/language. All derived images
    # inherit this split, preventing augmentation leakage into development.
    for group in GROUPS:
        for language in ("th", "en"):
            items = [x for x in documents if x["group"] == group and x["language"] == language]
            if len(items) < 6:
                raise ValueError(f"Too few labeled documents in {group}/{language}")
            for item in sorted(items, key=sort_key)[:3]:
                item["split"] = "test"

    return {
        "seed": SEED,
        "rule": "3 test PDFs per group/language; all augmentations inherit source PDF split",
        "documents": documents,
        "orphan_labels": sorted(orphan_labels),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    audit = build()
    path = OUT / "manifest.json"
    path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    counts = {split: sum(d["split"] == split for d in audit["documents"]) for split in ("dev", "test", "unlabeled")}
    print(f"Wrote {path.relative_to(ROOT)}: {counts}; orphan labels: {len(audit['orphan_labels'])}")


if __name__ == "__main__":
    main()
