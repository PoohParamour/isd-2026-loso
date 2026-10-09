"""Transcript App configuration loaded from transcript_app/.env."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


APP_DIR = Path(__file__).resolve().parent
PACKAGE_ROOT = APP_DIR.parent
PROJECT_ROOT = APP_DIR.parents[1]
load_dotenv(APP_DIR / ".env")


def _resolve_ocr_source() -> Path:
    """Locate the Lab 7/8 package in both the course and portable layouts."""
    configured = os.getenv("TRANSCRIPT_OCR_SOURCE_DIR")
    candidates = [
        Path(configured).expanduser() if configured else None,
        PACKAGE_ROOT / "src",
        PROJECT_ROOT / "src",
        PROJECT_ROOT / "Lab8a_ocr_system" / "src",
    ]
    for candidate in candidates:
        if candidate and (candidate / "ocr_system" / "lab7a_transcript.py").is_file():
            return candidate.resolve()
    # Return the documented layout so the startup error points to a useful path.
    return (PROJECT_ROOT / "src").resolve()


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("TRANSCRIPT_APP_NAME", "Transcript OCR Application")
    ollama_url: str = os.getenv("TRANSCRIPT_OLLAMA_URL", "http://127.0.0.1:11434")
    ocr_model: str = os.getenv(
        "TRANSCRIPT_OCR_MODEL", "scb10x/typhoon-ocr1.5-3b"
    )
    text_model: str = os.getenv("TRANSCRIPT_TEXT_MODEL", "qwen3:4b")
    max_upload_mb: int = int(os.getenv("TRANSCRIPT_MAX_UPLOAD_MB", "20"))
    max_image_side: int = int(os.getenv("TRANSCRIPT_MAX_IMAGE_SIDE", "1800"))
    ocr_source_dir: Path = _resolve_ocr_source()


settings = Settings()
