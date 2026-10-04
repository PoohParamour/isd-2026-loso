import unittest

from PIL import Image, ImageDraw

from model.extract import prefer_deskew_result
from model.photo_geometry import deskew_table


def extraction(courses, semesters=1, student_id="12345678", errors=0):
    return {
        "record": {
            "header_detail": {"student_id": student_id, "name": "Student"},
            "transcript_detail": {"semesters": [
                {"year": 2568, "subject": [{"subject_id": str(i).zfill(8)} for i in range(courses)]}
                for _ in range(semesters)]},
        },
        "validation": {"errors": errors},
    }


class DeskewSelectionTests(unittest.TestCase):
    def test_accepts_three_additional_valid_courses(self):
        self.assertTrue(prefer_deskew_result(extraction(5), extraction(8)))

    def test_rejects_small_gain_and_wrong_student(self):
        self.assertFalse(prefer_deskew_result(extraction(5), extraction(7)))
        self.assertFalse(prefer_deskew_result(extraction(5), extraction(8, student_id="87654321")))

    def test_accepts_added_course_and_dated_semester(self):
        self.assertTrue(prefer_deskew_result(extraction(8, semesters=7), extraction(9, semesters=8)))
        self.assertFalse(prefer_deskew_result(extraction(8, semesters=7), extraction(7, semesters=8)))

    def test_accepts_fewer_validation_errors_with_same_courses(self):
        self.assertTrue(prefer_deskew_result(extraction(9, errors=6), extraction(9, errors=1)))
        self.assertFalse(prefer_deskew_result(extraction(9, errors=2), extraction(9, errors=1)))

    def test_rejects_more_validation_errors(self):
        self.assertFalse(prefer_deskew_result(extraction(5), extraction(8, errors=1)))

    def test_damaged_identifiers_do_not_count(self):
        candidate = extraction(8)
        candidate["record"]["transcript_detail"]["semesters"][0]["subject"][0]["subject_id"] = "1234567"
        self.assertFalse(prefer_deskew_result(extraction(5), candidate))


class TableAngleTests(unittest.TestCase):
    def test_detects_small_table_tilt(self):
        image = Image.new("RGB", (1200, 1400), "white")
        drawing = ImageDraw.Draw(image)
        for y in range(150, 1250, 100):
            drawing.line((100, y, 1100, y + 35), fill="black", width=3)
        corrected = deskew_table(image)
        self.assertIsNotNone(corrected)
        self.assertAlmostEqual(corrected[1], 2.0, delta=0.5)

    def test_leaves_aligned_table_untouched(self):
        image = Image.new("RGB", (1200, 1400), "white")
        drawing = ImageDraw.Draw(image)
        for y in range(150, 1250, 100):
            drawing.line((100, y, 1100, y), fill="black", width=3)
        self.assertIsNone(deskew_table(image))


if __name__ == "__main__":
    unittest.main()
