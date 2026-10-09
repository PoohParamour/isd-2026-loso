"""Compare OCR models on the two photographed transcripts after PDF alignment."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from PIL import Image

from model.evaluate import evaluate_one
from model.extract import parse
from model.tools.train_photo_ocr import align


ROOT = Path(__file__).resolve().parents[2]
TESSERACT = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
MODELS = (
    ("installed_fast", Path(r"C:\Program Files\Tesseract-OCR\tessdata"), "eng"),
    ("photo_finetuned", ROOT / "model/data/photo_ocr", "eng_photo"),
)


def main() -> None:
    rows = []
    for stem in ("pooh", "doc"):
        photo_name = "1.jpg" if stem == "pooh" else "2.png"
        image = ROOT / f"tmp/photo_ocr_training/{stem}-aligned.png"
        image.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(align(ROOT / "data_transcript/input_new" / photo_name,
                              ROOT / "data_transcript/input_new" / f"{stem}.pdf")).save(image)
        truth = json.loads((ROOT / f"ground_truth_new/{stem}.json").read_text(encoding="utf-8"))
        models = list(MODELS)
        if (ROOT / "tmp/photo_ocr_training/eng_best.traineddata").exists():
            models.insert(1, ("trainable_best", ROOT / "tmp/photo_ocr_training", "eng_best"))
        for model_name, directory, language in models:
            for psm in (6, 11):
                process = subprocess.run(
                    [TESSERACT, str(image), "stdout", "-l", language, "--psm", str(psm),
                     "--tessdata-dir", str(directory)],
                    check=True, capture_output=True, encoding="utf-8", errors="replace",
                )
                prediction = parse(process.stdout, "bachelor_en")
                score = evaluate_one(prediction, truth)
                correct = sum(bucket["correct"] for bucket in score["categories"].values())
                total = sum(bucket["total"] for bucket in score["categories"].values())
                rows.append({
                    "source": stem, "model": model_name, "psm": psm,
                    "correct": correct, "total": total,
                    "field_accuracy": round(correct / total, 4),
                    "courses_detected": sum(len(s["subject"]) for s in prediction["transcript_detail"]["semesters"]),
                    "row_matches": score["rows"],
                })
                print(rows[-1], flush=True)
    path = ROOT / "model/reports/photo-ocr-fullpage.json"
    path.write_text(json.dumps({"note": "Same two source documents used for training; not a held-out document test",
                                "results": rows}, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
