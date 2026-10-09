"""Evaluate phone OCR by explicit angle split, with post-inference labels only."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import tempfile
import time
from pathlib import Path

from PIL import Image

from model.evaluate import evaluate_one, flatten, norm
from model.extract import extract, parse
from model.phone_table import read_phone_table
from model.photo_geometry import straighten_photo
from model.validate import validate_record

ROOT = Path(__file__).resolve().parents[2]


def evaluate(
    angles: list[int],
    output: Path,
    model_dir: Path | None,
    language: str,
    production: bool = False,
) -> dict:
    output.parent.mkdir(parents=True, exist_ok=True)
    details = []
    for person in ("peam", "pooh"):
        for angle in angles:
            path = ROOT / f"data_transcript/input_photo/{person}_photo{angle}.HEIC"
            started = time.monotonic()
            if production:
                result = extract(path)
            else:
                with Image.open(path) as source:
                    page = straighten_photo(source)
                if page is None:
                    raise RuntimeError(f"No reliable page boundary: {path.name}")
                with tempfile.TemporaryDirectory(prefix="isd_phone_eval_") as temp:
                    rect = Path(temp) / "page.png"
                    page.save(rect)
                    texts = read_phone_table(rect, model_dir, language)
                if texts is None:
                    raise RuntimeError(f"No reliable table: {path.name}")
                record = parse(texts[0], "bachelor_en", texts[1])
                result = {
                    "record": record,
                    "validation": validate_record(record),
                    "processing_seconds": round(time.monotonic() - started, 3),
                    "ocr_text": texts[0],
                    "body_text": texts[1],
                }
            # Labels are read strictly after inference has completed.
            truth = json.loads(
                (ROOT / f"ground_truth_new/{person}.json").read_text(encoding="utf-8")
            )
            score = evaluate_one(result["record"], truth)
            correct = sum(v["correct"] for v in score["categories"].values())
            total = sum(v["total"] for v in score["categories"].values())
            ref, hyp = flatten(truth), flatten(result["record"])
            errors = [
                {"field": k, "truth": v, "pred": hyp.get(k)}
                for k, v in ref.items()
                if norm(v, k) and norm(v, k) != norm(hyp.get(k), k)
            ]
            critical = {}
            for label, suffix in [
                ("student_id", ".student_id"),
                ("course_id", ".subject_id"),
                ("grade", ".grade_earn"),
                ("gpa", ".gpa"),
                ("gps", ".gps"),
                ("cumulative_gpa", ".cumulative_gpa"),
            ]:
                keys = [
                    k
                    for k, v in ref.items()
                    if k.lower().endswith(suffix) and norm(v, k)
                ]
                critical[label] = {
                    "correct": sum(
                        norm(ref[k], k) == norm(hyp.get(k), k) for k in keys
                    ),
                    "total": len(keys),
                }
            entry = {
                "image": path.name,
                "angle": angle,
                "correct": correct,
                "total": total,
                "accuracy": correct / total,
                "score": score,
                "critical": critical,
                "result": result,
                "errors": errors,
            }
            details.append(entry)
            report = summarize(details, model_dir, language)
            output.write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print(
                path.name,
                correct,
                total,
                score["rows"],
                result["processing_seconds"],
                flush=True,
            )
    return report


def summarize(details: list[dict], model_dir: Path | None, language: str) -> dict:
    correct = sum(d["correct"] for d in details)
    total = sum(d["total"] for d in details)
    rows = collections.Counter()
    critical = collections.defaultdict(collections.Counter)
    for detail in details:
        rows.update(detail["score"]["rows"])
        for label, values in detail["critical"].items():
            critical[label].update(values)
    precision = rows["tp"] / (rows["tp"] + rows["fp"]) if rows["tp"] + rows["fp"] else 0
    recall = rows["tp"] / (rows["tp"] + rows["fn"]) if rows["tp"] + rows["fn"] else 0
    model = model_dir / f"{language}.traineddata" if model_dir else None
    return {
        "evaluation": "same-document camera-angle evaluation; not independent document generalization",
        "images": len(details),
        "correct": correct,
        "total": total,
        "accuracy": correct / total,
        "rows": dict(rows),
        "row_f1": 2 * precision * recall / (precision + recall)
        if precision + recall
        else 0,
        "critical": {k: dict(v) for k, v in critical.items()},
        "mean_seconds": sum(d["result"]["processing_seconds"] for d in details)
        / len(details),
        "model_sha256": hashlib.sha256(model.read_bytes()).hexdigest()
        if model and model.exists()
        else None,
        "details": details,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--angles", nargs="+", type=int, choices=(1, 2, 3), required=True
    )
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path)
    parser.add_argument("--language", default="eng")
    parser.add_argument("--production", action="store_true")
    args = parser.parse_args()
    evaluate(args.angles, args.out, args.model_dir, args.language, args.production)


if __name__ == "__main__":
    main()
