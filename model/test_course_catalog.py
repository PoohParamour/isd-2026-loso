import unittest

from model.course_catalog import apply_course_catalog


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


if __name__ == "__main__":
    unittest.main()
