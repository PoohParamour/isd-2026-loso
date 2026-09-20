"""Conservative post-processing using a catalog trained on the dev split."""

from __future__ import annotations

import json
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


CATALOG_PATH = Path(__file__).parent / "data/course_catalog.json"


def load_catalog() -> dict[str, Any]:
    if not CATALOG_PATH.exists():
        return {}
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def _compact(value: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", value)).casefold()


def _entity_candidate(value: str, options: list[str]) -> str | None:
    if not value or not options:
        return None
    ranked = sorted(((SequenceMatcher(None, _compact(value), _compact(option)).ratio(), option) for option in options), reverse=True)
    best_score, best = ranked[0]
    runner_up = ranked[1][0] if len(ranked) > 1 else 0.0
    return best if best_score >= 0.72 and best_score - runner_up >= 0.04 else None


def apply_course_catalog(record: dict[str, Any], catalog: dict[str, Any] | None = None) -> dict[str, Any]:
    """Replace a course name only when its exact recognized code is known."""
    payload = load_catalog() if catalog is None else catalog
    courses = payload.get("courses", payload)
    entities = payload.get("entities", {})
    format_id = str(record.get("format_id") or "")
    header = record.get("header_detail", {})
    for field in ("faculty_name", "degree", "program"):
        candidate = _entity_candidate(str(header.get(field) or ""), entities.get(f"{format_id}:{field}", []))
        if candidate:
            header[field] = candidate
    for semester in record.get("transcript_detail", {}).get("semesters", []):
        for subject in semester.get("subject", []):
            code = str(subject.get("subject_id") or "")
            canonical = courses.get(f"{format_id}:{code}")
            if canonical:
                subject["subject_name"] = canonical
    return record
