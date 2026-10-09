"""Fine-tune English Tesseract line OCR on paired transcript photos/PDFs.

The PDF text layer supplies line labels; its rendered page is used only to
register each photo. A fifth of the course lines is held out before training.
Both documents contribute to training, so the holdout is at line level only.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path

import cv2
import numpy as np
import pdfplumber
import pypdfium2
from PIL import Image, ImageOps


ROOT = Path(__file__).resolve().parents[1]
PAIRS = (("pooh", "1.jpg"), ("doc", "2.png"))
INPUT = ROOT / "data_transcript/input_new"
LABELS = ROOT / "ground_truth_new"
TESSERACT_DIR = Path(r"C:\Program Files\Tesseract-OCR")


def executable(name: str) -> str:
    found = shutil.which(name) or str(TESSERACT_DIR / f"{name}.exe")
    if not Path(found).exists():
        raise FileNotFoundError(f"Missing {name}")
    return found


def run(*args: str, capture: bool = False) -> str:
    result = subprocess.run(args, check=True, text=True, encoding="utf-8", errors="replace",
                            stdout=subprocess.PIPE if capture else None,
                            stderr=subprocess.PIPE if capture else None)
    return result.stdout if capture else ""


def align(photo_path: Path, pdf_path: Path) -> np.ndarray:
    document = pypdfium2.PdfDocument(str(pdf_path))
    reference = np.asarray(document[0].render(scale=2).to_pil().convert("RGB"))
    photo = np.asarray(ImageOps.exif_transpose(Image.open(photo_path)).convert("RGB"))
    sift = cv2.SIFT_create(nfeatures=12000)
    ref_points, ref_descriptors = sift.detectAndCompute(cv2.cvtColor(reference, cv2.COLOR_RGB2GRAY), None)
    photo_points, photo_descriptors = sift.detectAndCompute(cv2.cvtColor(photo, cv2.COLOR_RGB2GRAY), None)
    pairs = cv2.BFMatcher().knnMatch(ref_descriptors, photo_descriptors, k=2)
    matches = [first for first, second in pairs if first.distance < 0.7 * second.distance]
    if len(matches) < 30:
        raise ValueError(f"Insufficient photo/PDF matches for {photo_path.name}: {len(matches)}")
    source = np.float32([ref_points[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
    target = np.float32([photo_points[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)
    matrix, inliers = cv2.findHomography(source, target, cv2.RANSAC, 5)
    if matrix is None or int(inliers.sum()) < 25:
        raise ValueError(f"Unreliable photo/PDF alignment for {photo_path.name}")
    return cv2.warpPerspective(photo, np.linalg.inv(matrix),
                               (reference.shape[1], reference.shape[0]),
                               flags=cv2.INTER_CUBIC, borderValue=(255, 255, 255))


def edit_distance(left: str, right: str) -> int:
    row = list(range(len(right) + 1))
    for i, char in enumerate(left, 1):
        next_row = [i]
        for j, other in enumerate(right, 1):
            next_row.append(min(next_row[-1] + 1, row[j] + 1,
                                row[j - 1] + (char != other)))
        row = next_row
    return row[-1]


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip()).upper()


def score(samples: list[dict], tessdata_dir: Path | None = None, language: str = "eng") -> dict:
    errors = characters = exact = 0
    for sample in samples:
        command = [executable("tesseract"), sample["path"], "stdout", "-l", language,
                   "--psm", "7"]
        if tessdata_dir:
            command.extend(["--tessdata-dir", str(tessdata_dir)])
        prediction = normalize(run(*command, capture=True))
        truth = normalize(sample["text"])
        errors += edit_distance(prediction, truth)
        characters += len(truth)
        exact += prediction == truth
    return {"lines": len(samples), "cer": round(errors / characters, 4),
            "exact_lines": exact, "characters": characters}


def prepare(work: Path) -> tuple[list[dict], list[dict]]:
    train, validation = [], []
    crops = work / "lines"
    crops.mkdir(parents=True, exist_ok=True)
    for stem, photo_name in PAIRS:
        truth = json.loads((LABELS / f"{stem}.json").read_text(encoding="utf-8"))
        expected_id = truth["header_detail"]["student_id"]
        pdf_path = INPUT / f"{stem}.pdf"
        image = align(INPUT / photo_name, pdf_path)
        with pdfplumber.open(pdf_path) as pdf:
            page = pdf.pages[0]
            lines = [line for line in page.extract_text_lines()
                     if re.match(r"^\d{8}\s", line["text"])]
            pdf_text = page.extract_text()
            if expected_id not in pdf_text:
                raise ValueError(f"Label/PDF student ID mismatch: {stem}")
        known_codes = {subject["subject_id"] for semester in truth["transcript_detail"]["semesters"]
                       for subject in semester["subject"]}
        for index, line in enumerate(lines):
            code = line["text"][:8]
            if code not in known_codes:
                raise ValueError(f"Course {code} missing from ground truth: {stem}")
            # PDF point coordinates map to the page rendered at 2 pixels/point.
            box = (max(0, int(line["x0"] * 2) - 4), max(0, int(line["top"] * 2) - 4),
                   min(image.shape[1], int(line["x1"] * 2) + 5),
                   min(image.shape[0], int(line["bottom"] * 2) + 5))
            crop = Image.fromarray(image[box[1]:box[3], box[0]:box[2]])
            crop = crop.resize((crop.width * 2, crop.height * 2), Image.Resampling.LANCZOS)
            path = crops / f"{stem}_{index:02d}.png"
            crop.save(path)
            path.with_suffix(".gt.txt").write_text(line["text"] + "\n", encoding="utf-8")
            sample = {"path": str(path), "text": line["text"], "source": stem, "code": code}
            (validation if index % 5 == 0 else train).append(sample)
    return train, validation


def train_model(work: Path, samples: list[dict], iterations: int, output: Path) -> None:
    starter = work / "eng_best.traineddata"
    if not starter.exists():
        raise FileNotFoundError("Download https://github.com/tesseract-ocr/tessdata_best/raw/refs/heads/main/eng.traineddata as eng_best.traineddata into the work directory")
    prefix = work / "eng"
    run(executable("combine_tessdata"), "-u", str(starter), str(prefix))
    lstmf_paths = []
    for sample in samples:
        path = Path(sample["path"])
        with Image.open(path) as line_image:
            width, height = line_image.size
        # Tesseract's line-level box format repeats the whole-line extent for
        # every character and ends with a tab marker.
        box = "".join(f"{char} 0 0 {width} {height} 0\n" for char in sample["text"])
        box += f"\t 0 0 {width} {height} 0\n"
        path.with_suffix(".box").write_text(box, encoding="utf-8")
        run(executable("tesseract"), str(path), str(path.with_suffix("")),
            "-l", "eng", "--psm", "7", "lstm.train")
        lstmf_paths.append(str(path.with_suffix(".lstmf")))
    listfile = work / "train.list"
    listfile.write_bytes(("\n".join(lstmf_paths) + "\n").encode("utf-8"))
    checkpoint = work / "eng_photo"
    run(executable("lstmtraining"), "--continue_from", str(prefix) + ".lstm",
        "--traineddata", str(starter), "--train_listfile", str(listfile),
        "--model_output", str(checkpoint), "--max_iterations", str(iterations))
    output.parent.mkdir(parents=True, exist_ok=True)
    run(executable("lstmtraining"), "--stop_training", "--continue_from",
        str(checkpoint) + "_checkpoint", "--traineddata", str(starter),
        "--model_output", str(output))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--evaluate-only", action="store_true")
    parser.add_argument("--work", type=Path, default=ROOT / "tmp/photo_ocr_training")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "model/data/photo_ocr/eng_photo.traineddata")
    parser.add_argument("--report", type=Path,
                        default=ROOT / "model/reports/photo-ocr-training.json")
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    train, validation = prepare(args.work)
    starter = args.work / "eng_best.traineddata"
    if not starter.exists():
        raise FileNotFoundError(f"Missing trainable starter model: {starter}")
    before = {"train": score(train, args.work, "eng_best"),
              "validation": score(validation, args.work, "eng_best")}
    print("Baseline:", before, flush=True)
    if not args.evaluate_only:
        train_model(args.work, train, args.iterations, args.output)
    after = {"train": score(train, args.output.parent, "eng_photo"),
             "validation": score(validation, args.output.parent, "eng_photo")}
    report = {"sources": [photo for _, photo in PAIRS], "training_lines": len(train),
              "held_out_lines": len(validation), "iterations": args.iterations,
              "split": "within-document line holdout; not an independent document test",
              "installed_fast_validation": score(validation),
              "before": before, "after": after, "model": str(args.output.relative_to(ROOT))}
    report["by_source"] = {
        source: {
            "before": score([row for row in validation if row["source"] == source], args.work, "eng_best"),
            "after": score([row for row in validation if row["source"] == source], args.output.parent, "eng_photo"),
        }
        for source, _ in PAIRS
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("Result:", report, flush=True)


if __name__ == "__main__":
    main()
