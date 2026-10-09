import unittest
import json
import tempfile
from pathlib import Path

from model.course_catalog import apply_course_catalog
from model.tools.train_course_catalog import build_catalog


class CourseCatalogTests(unittest.TestCase):
    def test_corrects_name_for_exact_code_and_format(self):
        record = {"format_id": "bachelor_th", "transcript_detail": {"semesters": [{"subject": [{"subject_id": "06026240", "subject_name": "ผิด"}]}]}}
        result = apply_course_catalog(record, {"courses": {"bachelor_th:06026240": "ระบบอัจฉริยะ"}})
        self.assertEqual(result["transcript_detail"]["semesters"][0]["subject"][0]["subject_name"], "ระบบอัจฉริยะ")

    def test_does_not_guess_unknown_code(self):
        record = {"format_id": "bachelor_th", "transcript_detail": {"semesters": [{"subject": [{"subject_id": "06026241", "subject_name": "อ่านได้"}]}]}}
        result = apply_course_catalog(record, {"courses": {"bachelor_th:06026240": "ระบบอัจฉริยะ"}})
        self.assertEqual(result["transcript_detail"]["semesters"][0]["subject"][0]["subject_name"], "อ่านได้")

    def test_corrects_close_header_entity(self):
        record = {"format_id": "graduate_th", "header_detail": {"faculty_name": "คณะจวทยาศาสตร"}, "transcript_detail": {"semesters": []}}
        catalog = {"entities": {"graduate_th:faculty_name": ["คณะวิทยาศาสตร์"]}}
        self.assertEqual(apply_course_catalog(record, catalog)["header_detail"]["faculty_name"], "คณะวิทยาศาสตร์")

    def test_training_excludes_whole_held_out_document(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for doc_id, course_id in (("a", "11111111"), ("b", "22222222")):
                record = {"transcript_detail": {"semesters": [
                    {"subject": [{"subject_id": course_id, "subject_name": doc_id}]}
                ]}}
                (root / f"{doc_id}.json").write_text(json.dumps(record), encoding="utf-8")
            manifest = {"documents": [
                {"id": doc_id, "split": "dev", "gt": f"{doc_id}.json",
                 "group": "bachelor", "language": "en"}
                for doc_id in ("a", "b")
            ]}
            held_out = build_catalog(manifest, exclude_ids=frozenset({"a"}), root=root)
            self.assertEqual(held_out["source_documents"], 1)
            self.assertEqual(held_out["courses"], {"bachelor_en:22222222": "b"})


if __name__ == "__main__":
    unittest.main()
