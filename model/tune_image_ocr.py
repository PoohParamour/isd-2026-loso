"""Tune image preprocessing and Tesseract layout mode on the dev split.

This script is deliberately separate from production inference. It selects a
configuration using dev labels only and never reads test labels.
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import tempfile
import time
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from evaluate import evaluate_one
from extract import ROOT, parse


PREPROCESSORS = ("original", "autocontrast", "threshold", "sharpen")
PSM_MODES = (4, 6, 11)


def preprocess(image: Image.Image, mode: str, scale: int) -> Image.Image:
    image = image.convert("RGB")
    image = image.resize((image.width * scale, image.height * scale), Image.Resampling.LANCZOS)
    if mode == "original":
        return image
    gray = ImageOps.grayscale(image)
    if mode == "autocontrast":
        return ImageOps.autocontrast(gray, cutoff=1)
    if mode == "threshold":
        gray = ImageOps.autocontrast(gray, cutoff=1)
        return gray.point(lambda value: 255 if value > 180 else 0)
    if mode == "sharpen":
        gray = ImageEnhance.Contrast(gray).enhance(1.5)
        return gray.filter(ImageFilter.UnsharpMask(radius=2, percent=180, threshold=3))
    raise ValueError(f"Unknown preprocessor: {mode}")


def tesseract(image: Image.Image, language: str, psm: int, work: Path, name: str) -> str:
    target = work / f"{name}.png"
    image.save(target)
    result = subprocess.run(
        ["tesseract", str(target), "stdout", "-l", language, "--psm", str(psm)],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def read_with_config(path: Path, format_id: str, mode: str, psm: int, scale: int) -> tuple[str, str]:
    language = "eng" if format_id.endswith("_en") else "tha+eng"
    with Image.open(path) as source, tempfile.TemporaryDirectory(prefix="ocr_tune_") as temp:
        work = Path(temp)
        full = preprocess(source, mode, scale)
        full_text = tesseract(full, language, psm, work, "full")
        if not format_id.startswith("bachelor_"):
            return full_text, full_text

        # Bachelor layouts use two reading columns. Crop before preprocessing
        # so each column is read top-to-bottom independently.
        width, height = source.size
        top, bottom = round(height * 0.185), round(height * 0.93)
        middle = width // 2
        chunks = []
        for name, box in (("left", (0, top, middle, bottom)), ("right", (middle, top, width, bottom))):
            crop = preprocess(source.crop(box), mode, scale)
            chunks.append(tesseract(crop, language, psm, work, name))
        return full_text, "\n".join(chunks)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-group", type=int, default=1)
    parser.add_argument("--scale", type=int, default=2)
    parser.add_argument("--preprocess", action="append", choices=PREPROCESSORS)
    parser.add_argument("--psm", action="append", type=int, choices=PSM_MODES)
    parser.add_argument("--save-text-dir", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    manifest = json.loads((ROOT / "model/data/manifest.json").read_text(encoding="utf-8"))
    images = {item.stem: item for item in (ROOT / "all/Lab5_transcript_dataset/images/original").rglob("*.png")}
    selected = []
    for group in ("bachelor", "graduate"):
        for language in ("th", "en"):
            docs = sorted(
                (doc for doc in manifest["documents"] if doc["split"] == "dev" and doc["group"] == group and doc["language"] == language),
                key=lambda doc: doc["id"],
            )
            selected.extend(docs[: args.per_group])

    rows = []
    preprocessors = tuple(args.preprocess or PREPROCESSORS)
    psm_modes = tuple(args.psm or PSM_MODES)
    for mode in preprocessors:
        for psm in psm_modes:
            for doc in selected:
                image = images.get(doc["id"])
                if image is None:
                    raise FileNotFoundError(doc["id"])
                format_id = f"{doc['group']}_{doc['language']}"
                started = time.monotonic()
                full_text, body_text = read_with_config(image, format_id, mode, psm, args.scale)
                if args.save_text_dir:
                    args.save_text_dir.mkdir(parents=True, exist_ok=True)
                    (args.save_text_dir / f"{doc['id']}__{mode}__psm{psm}.txt").write_text(
                        full_text + "\n\n=== BODY READING ORDER ===\n" + body_text,
                        encoding="utf-8",
                    )
                prediction = parse(full_text, format_id, body_text)
                truth = json.loads((ROOT / doc["gt"]).read_text(encoding="utf-8"))
                score = evaluate_one(prediction, truth)
                correct = sum(bucket["correct"] for bucket in score["categories"].values())
                total = sum(bucket["total"] for bucket in score["categories"].values())
                tp, fn, fp = (score["rows"][key] for key in ("tp", "fn", "fp"))
                precision = tp / (tp + fp) if tp + fp else 0
                recall = tp / (tp + fn) if tp + fn else 0
                row_f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0
                row = {
                    "id": doc["id"], "group": doc["group"], "language": doc["language"],
                    "preprocess": mode, "psm": psm, "scale": args.scale,
                    "seconds": round(time.monotonic() - started, 3),
                    "correct": correct, "total": total, "accuracy": correct / total,
                    "row_f1": row_f1,
                }
                rows.append(row)
                print(doc["id"], mode, psm, f"{correct}/{total}", flush=True)

    matrix = []
    for mode in preprocessors:
        for psm in psm_modes:
            subset = [row for row in rows if row["preprocess"] == mode and row["psm"] == psm]
            correct = sum(row["correct"] for row in subset)
            total = sum(row["total"] for row in subset)
            matrix.append({
                "preprocess": mode, "psm": psm, "scale": args.scale,
                "documents": len(subset), "correct": correct, "total": total,
                "accuracy": correct / total,
                "mean_row_f1": statistics.mean(row["row_f1"] for row in subset),
                "mean_seconds": statistics.mean(row["seconds"] for row in subset),
            })
    matrix.sort(key=lambda item: (item["accuracy"], item["mean_row_f1"]), reverse=True)
    report = {"split": "dev", "selection_only": True, "best": matrix[0], "matrix": matrix, "details": rows}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"best": matrix[0]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
