"""Evaluate structured transcript extraction against a locked document split.

Primary score: exact matches among non-empty reference fields. Missing output
counts as wrong. Course rows are aligned by semester and position for the field
score; an independent row precision/recall/F1 penalizes missing and extra rows.
"""

from __future__ import annotations

import argparse
import collections
import csv
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MONTHS_TH = {
    "มกราคม": 1, "กุมภาพันธ์": 2, "มีนาคม": 3, "เมษายน": 4,
    "พฤษภาคม": 5, "มิถุนายน": 6, "กรกฎาคม": 7, "สิงหาคม": 8,
    "กันยายน": 9, "ตุลาคม": 10, "พฤศจิกายน": 11, "ธันวาคม": 12,
}
MONTHS_EN = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}


def norm(value: Any, field: str = "") -> str:
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value)).strip().casefold()
    if text in {"", "none", "null", "n/a", "na", "0000-00-00"}:
        return ""
    if field.endswith(".honor") and text == "0":
        return ""  # No honor is an absent value, not an extracted field.
    if any(tag in field for tag in ("date", "updated_at")):
        iso = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
        if iso:
            return f"{int(iso[1]):04d}-{int(iso[2]):02d}-{int(iso[3]):02d}"
        for name, month in {**MONTHS_TH, **MONTHS_EN}.items():
            match = re.search(rf"(\d{{1,2}})\s+{re.escape(name)}[,]?\s+(\d{{4}})", text)
            if match:
                year = int(match[2])
                if year > 2400:
                    year -= 543
                return f"{year:04d}-{month:02d}-{int(match[1]):02d}"
    if any(tag in field for tag in ("gpa", "gps", "grade_earn")):
        try:
            if "grade_earn" not in field:
                return f"{float(text):.2f}"
        except ValueError:
            pass
    return re.sub(r"\s+", "", text)


def flatten(record: dict) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for section in ("header_detail", "footer_detail"):
        for key, value in (record.get(section) or {}).items():
            if isinstance(value, dict):
                for subkey, subvalue in value.items():
                    output[f"{section}.{key}.{subkey}"] = subvalue
            else:
                output[f"{section}.{key}"] = value
    transcript = record.get("transcript_detail") or {}
    for key, value in transcript.items():
        if key != "semesters":
            output[f"transcript_detail.{key}"] = value
    for si, semester in enumerate(transcript.get("semesters") or []):
        for key, value in semester.items():
            if key != "subject":
                output[f"semesters[{si}].{key}"] = value
        for ci, subject in enumerate(semester.get("subject") or []):
            for key, value in subject.items():
                output[f"semesters[{si}].subject[{ci}].{key}"] = value
    return output


def distance(a: str, b: str) -> int:
    previous = list(range(len(b) + 1))
    for i, char_a in enumerate(a, 1):
        current = [i]
        for j, char_b in enumerate(b, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (char_a != char_b)))
        previous = current
    return previous[-1]


def category(path: str) -> str:
    if ".subject[" in path:
        return "course"
    if path.startswith("semesters["):
        return "semester"
    if path.startswith("header_detail"):
        return "header"
    if path.startswith("footer_detail"):
        return "footer"
    return "summary"


def row_keys(record: dict) -> collections.Counter:
    rows: collections.Counter = collections.Counter()
    for semester in (record.get("transcript_detail") or {}).get("semesters") or []:
        year = norm(semester.get("year"))
        number = norm(semester.get("sem_num"))
        for subject in semester.get("subject") or []:
            code = norm(subject.get("subject_id"))
            if code:
                rows[(year, number, code)] += 1
    return rows


def evaluate_one(pred: dict, gt: dict) -> dict:
    refs = flatten(gt)
    hyps = flatten(pred)
    counts = collections.defaultdict(lambda: {"correct": 0, "total": 0, "edits": 0, "chars": 0, "hallucinated": 0})
    for field, value in refs.items():
        ref = norm(value, field)
        hyp = norm(hyps.get(field), field)
        bucket = counts[category(field)]
        if ref:
            bucket["total"] += 1
            bucket["correct"] += int(ref == hyp)
            bucket["edits"] += distance(ref, hyp)
            bucket["chars"] += len(ref)
        elif hyp:
            bucket["hallucinated"] += 1
    # Extra output fields and rows are counted as hallucinations, separately
    # from the non-empty-reference primary accuracy.
    for field in hyps.keys() - refs.keys():
        if norm(hyps[field], field):
            counts[category(field)]["hallucinated"] += 1
    truth_rows, predicted_rows = row_keys(gt), row_keys(pred)
    matched = sum((truth_rows & predicted_rows).values())
    tp, fn, fp = matched, sum(truth_rows.values()) - matched, sum(predicted_rows.values()) - matched
    return {"categories": dict(counts), "rows": {"tp": tp, "fn": fn, "fp": fp}}


def aggregate(documents: list[dict], split: str, pred_dir: Path) -> tuple[dict, list[dict]]:
    buckets = collections.defaultdict(lambda: collections.Counter())
    detail: list[dict] = []
    for doc in documents:
        if doc["split"] != split or not doc["gt"]:
            continue
        gt = json.loads((ROOT / doc["gt"]).read_text(encoding="utf-8"))
        pred_path = pred_dir / f"{doc['id']}.json"
        pred = json.loads(pred_path.read_text(encoding="utf-8")) if pred_path.exists() else {}
        if "record" in pred and isinstance(pred["record"], dict):
            pred = pred["record"]
        result = evaluate_one(pred, gt)
        for label in ("overall", doc["group"], doc["language"], f"{doc['group']}_{doc['language']}"):
            for cat, values in result["categories"].items():
                buckets[(label, cat)].update(values)
            buckets[(label, "rows")].update(result["rows"])
        total = sum(v["total"] for v in result["categories"].values())
        correct = sum(v["correct"] for v in result["categories"].values())
        detail.append({"id": doc["id"], "group": doc["group"], "language": doc["language"], "predicted": pred_path.exists(), "correct": correct, "total": total, "accuracy": correct / total if total else 0})

    matrix = []
    primary = collections.Counter()
    for (label, cat), values in buckets.items():
        if label == "overall" and cat != "rows":
            primary.update(values)
    for (label, cat), v in sorted(buckets.items()):
        if cat == "rows":
            tp, fn, fp = v["tp"], v["fn"], v["fp"]
            precision = tp / (tp + fp) if tp + fp else 0
            recall = tp / (tp + fn) if tp + fn else 0
            matrix.append({"slice": label, "category": cat, "tp": tp, "fn": fn, "fp": fp, "precision": precision, "recall": recall, "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0})
        else:
            total = v["total"]
            matrix.append({"slice": label, "category": cat, "correct": v["correct"], "total": total, "accuracy": v["correct"] / total if total else 0, "cer": v["edits"] / v["chars"] if v["chars"] else 0, "hallucinated": v["hallucinated"]})
    report = {
        "split": split,
        "documents": len(detail),
        "primary_exact_field_accuracy": primary["correct"] / primary["total"] if primary["total"] else 0,
        "primary_correct": primary["correct"],
        "primary_total": primary["total"],
        "target_met": primary["total"] > 0 and primary["correct"] / primary["total"] > 0.91,
        "matrix": matrix,
    }
    return report, detail


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=ROOT / "model/data/manifest.json")
    parser.add_argument("--pred-dir", type=Path, required=True)
    parser.add_argument("--split", choices=("dev", "test"), default="dev")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    report, detail = aggregate(manifest["documents"], args.split, args.pred_dir)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if detail:
        with (args.out / "documents.csv").open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=list(detail[0]))
            writer.writeheader()
            writer.writerows(detail)
    print(json.dumps({"split": args.split, "documents": len(detail), "primary_exact_field_accuracy": report["primary_exact_field_accuracy"], "target_met": report["target_met"], "overall_matrix": [x for x in report["matrix"] if x["slice"] == "overall"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
