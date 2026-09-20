"""Build a course-name catalog from the manifest's development split only."""

from __future__ import annotations

import collections
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "model/data/manifest.json"
OUTPUT = ROOT / "model/data/course_catalog.json"


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    values: dict[tuple[str, str, str], collections.Counter[str]] = collections.defaultdict(collections.Counter)
    entities: dict[tuple[str, str], set[str]] = collections.defaultdict(set)
    source_documents = 0
    for document in manifest["documents"]:
        if document["split"] != "dev" or not document.get("gt"):
            continue
        source_documents += 1
        record = json.loads((ROOT / document["gt"]).read_text(encoding="utf-8"))
        format_id = f"{document['group']}_{document['language']}"
        for field in ("faculty_name", "degree", "program"):
            value = str(record.get("header_detail", {}).get(field) or "")
            if value:
                entities[(format_id, field)].add(value)
        for semester in record.get("transcript_detail", {}).get("semesters", []):
            for subject in semester.get("subject", []):
                code = str(subject.get("subject_id") or "")
                name = str(subject.get("subject_name") or "")
                if len(code) == 8 and name:
                    values[(document["group"], document["language"], code)][name] += 1
    courses = {}
    ambiguous = []
    for (group, language, code), names in sorted(values.items()):
        if len(names) != 1:
            ambiguous.append({"group": group, "language": language, "code": code, "names": dict(names)})
            continue
        courses[f"{group}_{language}:{code}"] = next(iter(names))
    payload = {
        "training_split": "dev",
        "source_documents": source_documents,
        "courses": courses,
        "entities": {f"{format_id}:{field}": sorted(options) for (format_id, field), options in sorted(entities.items())},
        "ambiguous_excluded": ambiguous,
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT.relative_to(ROOT)} with {len(courses)} courses from {source_documents} dev documents")


if __name__ == "__main__":
    main()
