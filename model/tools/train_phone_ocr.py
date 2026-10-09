"""Reproducible phone-image LSTM fine-tuning with a sealed third-angle test.

Reference PDFs are used only to locate supervised training/validation crops.
The inference pipeline never receives a PDF, document identity, or label.
Angles 1/2 are train/validation; angle 3 is not opened by this module.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import shutil
from pathlib import Path

import cv2
import numpy as np
import pdfplumber
import pypdfium2
from PIL import Image, ImageOps
from pillow_heif import register_heif_opener

from model.tools.train_photo_ocr import executable, run, score

register_heif_opener()
ROOT = Path(__file__).resolve().parents[2]
SCALE = 3.2


def aligned_photo(photo: Path, pdf: Path) -> tuple[np.ndarray, dict]:
    with pypdfium2.PdfDocument(str(pdf)) as document:
        reference = np.asarray(document[0].render(scale=SCALE).to_pil().convert("RGB"))
    with Image.open(photo) as source:
        original = np.asarray(ImageOps.exif_transpose(source).convert("RGB"))
    sift = cv2.SIFT_create(nfeatures=18000)
    ref_points, ref_descriptors = sift.detectAndCompute(
        cv2.cvtColor(reference, cv2.COLOR_RGB2GRAY), None
    )
    photo_points, photo_descriptors = sift.detectAndCompute(
        cv2.cvtColor(original, cv2.COLOR_RGB2GRAY), None
    )
    matches = [
        a
        for a, b in cv2.BFMatcher().knnMatch(ref_descriptors, photo_descriptors, k=2)
        if a.distance < 0.7 * b.distance
    ]
    if len(matches) < 30:
        raise ValueError(f"Insufficient registration evidence: {photo.name}")
    source = np.float32([photo_points[m.trainIdx].pt for m in matches])
    target = np.float32([ref_points[m.queryIdx].pt for m in matches])
    matrix, mask = cv2.findHomography(source, target, cv2.RANSAC, 4)
    count = int(mask.sum()) if mask is not None else 0
    if matrix is None or count < 25 or count / len(matches) < 0.3:
        raise ValueError(
            f"Unreliable registration: {photo.name}, {count}/{len(matches)}"
        )
    warped = cv2.warpPerspective(
        original,
        matrix,
        (reference.shape[1], reference.shape[0]),
        flags=cv2.INTER_CUBIC,
        borderValue=(255, 255, 255),
    )
    return warped, {"matches": len(matches), "inliers": count}


def prepare(work: Path) -> dict:
    random.seed(42)
    crops = work / "lines"
    crops.mkdir(parents=True, exist_ok=True)
    samples, registration = [], {}
    for person in ("peam", "pooh"):
        pdf = ROOT / f"data_transcript/input_new/{person}.pdf"
        truth = json.loads(
            (ROOT / f"ground_truth_new/{person}.json").read_text(encoding="utf-8")
        )
        with pdfplumber.open(pdf) as document:
            page = document.pages[0]
            lines = page.extract_text_lines()
            if truth["header_detail"]["student_id"] not in page.extract_text():
                raise ValueError("Reference/label identity mismatch")
        known = {
            course["subject_id"]
            for sem in truth["transcript_detail"]["semesters"]
            for course in sem["subject"]
        }
        for angle, split in ((1, "train"), (2, "validation")):
            photo = ROOT / f"data_transcript/input_photo/{person}_photo{angle}.HEIC"
            aligned, diagnostics = aligned_photo(photo, pdf)
            registration[photo.name] = diagnostics
            Image.fromarray(aligned).save(work / f"{person}{angle}-aligned.png")
            for index, line in enumerate(lines):
                text = line["text"]
                # Dates can differ between printed exports. Exclude signatures,
                # issue dates, borders and sparse decorative labels entirely.
                if re.search(
                    r"Date Issued|Checked by|Xxxxx|Transcript Closed|COURSE TITLE|^Photo$",
                    text,
                    re.IGNORECASE,
                ):
                    continue
                if re.match(r"^\d{8}\s", text) and text[:8] not in known:
                    raise ValueError("Reference course not in supplied labels")
                boxes = [(line["x0"], line["top"], line["x1"], line["bottom"], text)]
                # Sparse multi-column header lines are better supervised as
                # two independent lines, rather than training whitespace gaps.
                if re.search(r"Student ID|Date of Admission|Date of Graduation", text):
                    words = line["chars"]
                    boxes = []
                    for side in (0, 1):
                        chars = [w for w in words if (w["x0"] < 350) == (side == 0)]
                        if chars:
                            label = "".join(w["text"] for w in chars).strip()
                            boxes.append(
                                (
                                    min(w["x0"] for w in chars),
                                    line["top"],
                                    max(w["x1"] for w in chars),
                                    line["bottom"],
                                    label,
                                )
                            )
                for part, (left, top, right, bottom, label) in enumerate(boxes):
                    l, t = (
                        max(0, round(left * SCALE) - 5),
                        max(0, round(top * SCALE) - 5),
                    )
                    r, b = (
                        min(aligned.shape[1], round(right * SCALE) + 6),
                        min(aligned.shape[0], round(bottom * SCALE) + 6),
                    )
                    crop = Image.fromarray(aligned[t:b, l:r]).convert("L")
                    # Illumination normalization matches inference preprocessing.
                    gray = np.asarray(crop)
                    norm = cv2.divide(
                        gray, cv2.GaussianBlur(gray, (0, 0), 8), scale=255
                    )
                    crop = ImageOps.expand(Image.fromarray(norm), 8, "white")
                    path = crops / f"{person}{angle}-{index:02d}-{part}.png"
                    crop.save(path)
                    path.with_suffix(".gt.txt").write_text(
                        label + "\n", encoding="utf-8"
                    )
                    samples.append(
                        {
                            "path": str(path),
                            "text": label,
                            "split": split,
                            "source": person,
                            "angle": angle,
                            "line": index,
                        }
                    )
    manifest = {
        "split": "angle 1 train / angle 2 validation / angle 3 sealed final test; same two documents",
        "seed": 42,
        "registration": registration,
        "samples": samples,
        "input_hashes": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (ROOT / "data_transcript/input_photo").glob("*.HEIC")
        },
    }
    (work / "samples.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "counts": {
                    s: sum(x["split"] == s for x in samples)
                    for s in ("train", "validation")
                },
                "registration": registration,
            }
        ),
        flush=True,
    )
    return manifest


def make_lstmf(samples: list[dict], starter: Path, work: Path) -> Path:
    paths = []
    config = work / "lstm.train"
    installed_config = (
        Path(executable("tesseract")).parent / "tessdata/configs/lstm.train"
    )
    if installed_config.exists():
        shutil.copy2(installed_config, config)
    else:
        config.write_text(
            "tessedit_train_line_recognizer T\ntessedit_init_config_only T\n",
            encoding="utf-8",
        )
    for sample in samples:
        path = Path(sample["path"])
        with Image.open(path) as image:
            width, height = image.size
        path.with_suffix(".box").write_text(
            "".join(f"{c} 0 0 {width} {height} 0\n" for c in sample["text"])
            + f"\t 0 0 {width} {height} 0\n",
            encoding="utf-8",
        )
        run(
            executable("tesseract"),
            str(path),
            str(path.with_suffix("")),
            "-l",
            starter.stem,
            "--tessdata-dir",
            str(starter.parent),
            "--oem",
            "1",
            "--psm",
            "7",
            str(config),
            capture=True,
        )
        if not path.with_suffix(".lstmf").exists():
            raise RuntimeError(f"Training example not generated: {path}")
        paths.append(str(path.with_suffix(".lstmf")))
    random.Random(42).shuffle(paths)
    listfile = work / (
        "train.list" if samples[0]["split"] == "train" else "validation.list"
    )
    # Windows Tesseract's list reader treats CR as part of the filename.
    listfile.write_bytes(("\n".join(paths) + "\n").encode("utf-8"))
    return listfile


def train(work: Path, iterations: int, learning_rate: float) -> Path:
    manifest = json.loads((work / "samples.json").read_text(encoding="utf-8"))
    starter = work / "eng_best.traineddata"
    if not starter.exists():
        shutil.copy2(ROOT / "tmp/photo_ocr_training/eng_best.traineddata", starter)
    prefix = work / "starter"
    if not prefix.with_suffix(".lstm").exists():
        run(
            executable("combine_tessdata"),
            "-e",
            str(starter),
            str(prefix.with_suffix(".lstm")),
            capture=True,
        )
    train_samples = [s for s in manifest["samples"] if s["split"] == "train"]
    val_samples = [s for s in manifest["samples"] if s["split"] == "validation"]
    for samples in (train_samples, val_samples):
        name = "train.list" if samples[0]["split"] == "train" else "validation.list"
        if not (work / name).exists() or any(
            not Path(s["path"]).with_suffix(".lstmf").exists() for s in samples
        ):
            make_lstmf(samples, starter, work)
        else:
            (work / name).write_bytes(
                (work / name).read_bytes().replace(b"\r\n", b"\n")
            )
    candidate = work / f"iter{iterations}-lr{learning_rate:g}"
    candidate.mkdir(exist_ok=True)
    checkpoint = candidate / "phone"
    run(
        executable("lstmtraining"),
        "--continue_from",
        str(prefix.with_suffix(".lstm")),
        "--traineddata",
        str(starter),
        "--train_listfile",
        str(work / "train.list"),
        "--eval_listfile",
        str(work / "validation.list"),
        "--model_output",
        str(checkpoint),
        "--learning_rate",
        str(learning_rate),
        "--max_iterations",
        str(iterations),
        "--target_error_rate",
        "0.01",
        "--debug_interval",
        "0",
    )
    output = candidate / "eng_phone.traineddata"
    run(
        executable("lstmtraining"),
        "--stop_training",
        "--continue_from",
        str(checkpoint) + "_checkpoint",
        "--traineddata",
        str(starter),
        "--model_output",
        str(output),
    )
    report = {
        "iterations": iterations,
        "learning_rate": learning_rate,
        "train": score(train_samples, candidate, "eng_phone"),
        "validation": score(val_samples, candidate, "eng_phone"),
    }
    (candidate / "metrics.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps(report), flush=True)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "baseline", "train"))
    parser.add_argument("--work", type=Path, default=ROOT / "tmp/phone_training")
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--learning-rate", type=float, default=0.0001)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    os.environ["OMP_THREAD_LIMIT"] = "2"
    if args.action == "prepare":
        prepare(args.work)
    elif args.action == "train":
        train(args.work, args.iterations, args.learning_rate)
    else:
        manifest = json.loads((args.work / "samples.json").read_text(encoding="utf-8"))
        samples = [s for s in manifest["samples"] if s["split"] == "validation"]
        if not (args.work / "eng_best.traineddata").exists():
            shutil.copy2(
                ROOT / "tmp/photo_ocr_training/eng_best.traineddata",
                args.work / "eng_best.traineddata",
            )
        report = {
            "installed": score(samples),
            "old_photo": score(samples, ROOT / "model/data/photo_ocr", "eng_photo"),
            "best": score(samples, args.work, "eng_best"),
        }
        (args.work / "line-baseline.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        print(json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
