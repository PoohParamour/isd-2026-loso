import unittest
from pathlib import Path
from unittest.mock import patch

from model.extract import extract
from model.layout_ocr import CodeBox, _column_starts


class LayoutDetectionTests(unittest.TestCase):
    def test_finds_columns_from_repeated_code_positions_after_shift(self):
        boxes = [CodeBox(x, y, 90, 18) for x in (120, 124, 118, 730, 728, 734) for y in (250,)]
        boxes.append(CodeBox(940, 60, 90, 18))  # Student ID, not a course column.
        self.assertEqual(_column_starts(boxes), [120, 730])
        shifted = [CodeBox(box.left + 375, box.top + 210, box.width, box.height) for box in boxes]
        self.assertEqual(_column_starts(shifted), [495, 1105])

    def test_does_not_treat_an_isolated_id_as_a_column(self):
        self.assertEqual(_column_starts([CodeBox(450, 50, 90, 18)]), [])

    @patch("model.layout_ocr.read_layout_body", return_value="1st Semester, 2021\n12345678 Introduction to Computing 3 A")
    @patch("model.extract.read_image_profile", return_value=("Student ID 87654321", ""))
    @patch("model.extract.read_document", return_value=("Student ID 87654321", "tesseract"))
    def test_auto_uses_detected_rows_when_profile_has_no_course(self, _document, _profile, detected):
        result = extract(Path("sample.png"), format_id="bachelor_en")
        subjects = result["record"]["transcript_detail"]["semesters"][0]["subject"]
        self.assertEqual(subjects[0]["subject_id"], "12345678")
        detected.assert_called_once()

    @patch("model.layout_ocr.read_layout_body", return_value="1st Semester, 2021\n12345678 Introduction to Computing 3 A")
    @patch("model.extract.read_image_profile", side_effect=AssertionError("fixed crop used"))
    @patch("model.extract.read_document", return_value=("Student ID 87654321", "tesseract"))
    def test_detected_mode_never_uses_fixed_crop(self, _document, _profile, detected):
        result = extract(Path("sample.png"), format_id="bachelor_en", image_layout="detected")
        self.assertEqual(result["record"]["transcript_detail"]["semesters"][0]["subject"][0]["subject_id"], "12345678")
        detected.assert_called_once()

    @patch("model.layout_ocr.read_layout_body", return_value="1st Semester, 2021\n12345678 Introduction to Computing 3 A")
    @patch("model.extract.read_image_profile", side_effect=AssertionError("fixed crop used"))
    @patch("model.extract.read_document", return_value=("( Unofficial Transcript )\nStudent ID 87654321", "tesseract"))
    def test_auto_uses_detected_layout_for_unofficial_heading(self, _document, _profile, detected):
        result = extract(Path("sample.png"), format_id="bachelor_en")
        self.assertEqual(result["record"]["transcript_detail"]["semesters"][0]["subject"][0]["subject_id"], "12345678")
        detected.assert_called_once()


if __name__ == "__main__":
    unittest.main()
