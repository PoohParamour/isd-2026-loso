import unittest
from pathlib import Path
from unittest.mock import patch

from model.extract import cumulative_gpa_from_sources, extract, parse_summary


class GPARecoveryTests(unittest.TestCase):
    def test_extra_leading_digit_is_rejected_without_guessing(self):
        self.assertIsNone(parse_summary(["Cumulative GPA: 23.34"], "en")["cumulative_gpa"])
        self.assertEqual(cumulative_gpa_from_sources([
            "Cumulative GPA: 23.34", "Cumulative GPA: 3.34"], "en"), "3.34")
        self.assertIsNone(cumulative_gpa_from_sources(["Cumulative GPA: 23.34"], "en"))

    @patch("model.extract.read_document", return_value=("Student ID 12345678\nCumulative GPA: 23.34", "tesseract"))
    @patch("model.extract.read_bachelor_columns", return_value="Cumulative GPA: 3.34\n1st Semester, 2024\n12345678 EXAMPLE COURSE 3 A")
    def test_pdf_uses_clean_existing_column_pass(self, columns, document):
        result = extract(Path("nonexistent-gpa-test.pdf"), format_id="bachelor_en", force_ocr=True)
        self.assertEqual(result["record"]["transcript_detail"]["cumulative_gpa"], "3.34")
        self.assertEqual(result["validation"]["course_count"], 1)

    @patch("model.extract.read_document", return_value=("Student ID 12345678\nCumulative GPA: 23.34", "tesseract"))
    @patch("model.extract.read_bachelor_columns", return_value="1st Semester, 2024\n12345678 EXAMPLE COURSE 3 A")
    def test_unrecoverable_pdf_gpa_requires_review(self, columns, document):
        result = extract(Path("nonexistent-gpa-test.pdf"), format_id="bachelor_en", force_ocr=True)
        self.assertIsNone(result["record"]["transcript_detail"]["cumulative_gpa"])
        self.assertTrue(result["validation"]["needs_review"])
        self.assertTrue(any(issue["code"] == "unreadable_cumulative_gpa"
                            for issue in result["validation"]["issues"]))

    def test_reads_explicit_cumulative_value_from_another_pass(self):
        self.assertEqual(cumulative_gpa_from_sources([
            "Cumulative GPA: 242", "GPA: 3.50\nCumulative GPA: 2.42"], "en"), "2.42")

    def test_does_not_invent_decimal_or_reuse_semester_gpa(self):
        self.assertIsNone(cumulative_gpa_from_sources(["Cumulative GPA: 242\nGPS: 3.50 GPA: 2.42"], "en"))

    def test_conflicting_values_are_not_selected(self):
        self.assertIsNone(cumulative_gpa_from_sources(["Cumulative GPA: 2.42\nCumulative GPA: 2.47"], "en"))

    def test_rejects_out_of_range_value(self):
        self.assertIsNone(cumulative_gpa_from_sources(["Cumulative GPA: 12.42"], "en"))

    def test_thai_label_and_zero_value(self):
        self.assertEqual(cumulative_gpa_from_sources(["คะแนนเฉลี่ยสะสม : 0.00"], "th"), "0.00")

    @patch("model.extract.read_document", return_value=("Unofficial Transcript\nStudent ID 12345678\nCumulative GPA: 242", "tesseract"))
    @patch("model.layout_ocr.read_layout_body", return_value="1st Semester, 2024\n12345678 EXAMPLE COURSE 3 B+\nCumulative GPA: 2.42")
    def test_extract_recovers_gpa_without_changing_course(self, layout, document):
        result = extract(Path("nonexistent-gpa-test.png"), format_id="bachelor_en")
        detail = result["record"]["transcript_detail"]
        self.assertEqual(detail["cumulative_gpa"], "2.42")
        self.assertEqual(detail["semesters"][0]["subject"], [{
            "subject_id": "12345678", "subject_name": "EXAMPLE COURSE",
            "type": None, "credit": 3, "grade_earn": "b+"}])
        layout.assert_called_once()
        document.assert_called_once()

    @patch("model.extract.read_document", return_value=("Unofficial Transcript\nCumulative GPA: 3.10", "tesseract"))
    @patch("model.layout_ocr.read_layout_body", return_value="12345678 EXAMPLE COURSE 3 B+\nCumulative GPA: 2.42")
    def test_existing_gpa_is_preserved(self, layout, document):
        result = extract(Path("nonexistent-gpa-test.png"), format_id="bachelor_en")
        self.assertEqual(result["record"]["transcript_detail"]["cumulative_gpa"], "3.10")


if __name__ == "__main__":
    unittest.main()
