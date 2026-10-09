import unittest

from model.extract import parse_courses, parse_header, parse_term


class ScreenTableParsingTests(unittest.TestCase):
    def test_heading_repairs_are_shared_by_parser_and_ocr_selection(self):
        self.assertEqual(parse_term('Ist Semester, Year, 2024-2025', 'en'), (1, 2567))
        self.assertEqual(parse_term('Ist Sermester, Yeur, 2026-2027', 'en'), (1, 2569))

    def test_missing_cells_preserve_row_and_wrapped_name(self):
        semesters = parse_courses([
            '1st Semester, Year, 2024-2025',
            '12345678 INTRODUCTION TO NETWORKS AND ? B+',
            'CYBERSECURITY',
            '? ANOTHER COURSE 3 ?',
        ], 'en', False)
        courses = semesters[0]['subject']
        self.assertEqual(len(courses), 2)
        self.assertEqual(courses[0]['subject_name'], 'INTRODUCTION TO NETWORKS AND CYBERSECURITY')
        self.assertIsNone(courses[0]['credit'])
        self.assertEqual(courses[0]['grade_earn'], 'b+')
        self.assertIsNone(courses[1]['subject_id'])
        self.assertIsNone(courses[1]['grade_earn'])

    def test_unreadable_student_id_does_not_use_first_course_code(self):
        header = parse_header(['Unofficial Transcript', 'Student ID 1234567',
                               '87654321 EXAMPLE COURSE 3 A'], 'en')
        self.assertIsNone(header['student_id'])


if __name__ == '__main__':
    unittest.main()
