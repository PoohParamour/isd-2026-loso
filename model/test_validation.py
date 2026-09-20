import unittest

from model.extract import parse_courses, parse_header, parse_term
from model.validate import validate_record


class ValidateRecordTests(unittest.TestCase):
    def test_student_id_can_be_on_separate_line(self):
        header = parse_header(["Student Name: Jane Example", "Registration No: 12345678", "Faculty of Engineering"], "en")
        self.assertEqual(header["student_id"], "12345678")
        self.assertEqual(header["name"], "Jane Example")
        self.assertEqual(header["faculty_name"], "Faculty of Engineering")

    def test_alternate_semester_headings(self):
        self.assertEqual(parse_term("ปีการศึกษา 2567 ภาคเรียนที่ 2", "th"), (2, 2567))
        self.assertEqual(parse_term("Academic Year 2024 Semester 1", "en"), (1, 2567))

    def test_courses_without_known_semester_are_preserved(self):
        rows = parse_courses(["06026240 Intelligent Systems 3 A"], "en", False)
        self.assertEqual(rows[0]["sem_num"], 0)
        self.assertIsNone(rows[0]["year"])
        self.assertEqual(rows[0]["subject"][0]["subject_id"], "06026240")

    def test_thai_semester_marker_tolerates_missing_tone_mark(self):
        rows = parse_courses(
            ["ภาคการศึกษาที 2 ปีการศึกษา 2563", "05208101 สัมมนาปริญญาเอก 1 Cr 1 S"],
            "th",
            True,
        )
        self.assertEqual(rows[0]["year"], 2563)
        self.assertEqual(rows[0]["subject"][0]["subject_id"], "05208101")

    def test_thai_gps_accepts_legacy_sara_am_and_missing_tone(self):
        rows = parse_courses(
            ["ภาคการศึกษาที 2 ปีการศึกษา 2563", "คะแนนเฉลียประจําภาคการศึกษา : 3.50 คะแนนเฉลี่ย : 3.25"],
            "th",
            True,
        )
        self.assertEqual(rows[0]["GPS"], "3.50")
        self.assertEqual(rows[0]["GPA"], "3.25")

    def test_valid_minimal_record(self):
        record = {
            "header_detail": {"student_id": "71010001", "name": "Test", "faculty_name": "IT", "program": "IT"},
            "transcript_detail": {"semesters": [{"year": 2567, "sem_num": 1, "GPA": "3.00", "GPS": "3.00", "subject": [{"subject_id": "06026240", "credit": 3, "grade_earn": "a"}]}]},
        }
        result = validate_record(record)
        self.assertFalse(result["needs_review"])
        self.assertEqual(result["course_count"], 1)

    def test_invalid_values_are_flagged(self):
        record = {
            "header_detail": {"student_id": "ABC"},
            "transcript_detail": {"semesters": [{"year": 67, "sem_num": 9, "GPA": "5.00", "subject": [{"subject_id": "x", "credit": -1, "grade_earn": "z"}]}]},
        }
        result = validate_record(record)
        self.assertTrue(result["needs_review"])
        self.assertGreaterEqual(result["errors"], 4)


if __name__ == "__main__":
    unittest.main()
