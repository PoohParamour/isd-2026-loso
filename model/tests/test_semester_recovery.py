import unittest

from model.extract import parse_courses, recover_semester_headings


class SemesterRecoveryTests(unittest.TestCase):
    primary = "\n".join([
        "2nd Semester, Year, 2024-2025",
        "12345670 EARLIER COURSE 3 S", "GPS: 1.70 GPA: 1.88",
        "12345671 DATABASE SYSTEM CONCEPTS 3 B+",
        "12345672 FUNDAMENTAL WEB PROGRAMMING 3 A", "GPS: 2.17 GPA: 1.95",
        "2nd Semester, Year, 2025-2026", "12345673 LATER COURSE 3 C",
    ])
    reference = "\n".join([
        "2nd Semester, Year, 2024-2025", "EARLIER COURSE",
        "1st Semester, Year, 2025-2026", "DATABASE SYSTEM CONCEPTS",
        "FUNDAMENTAL WEB PROGRAMMING", "GPS: 2.17 GPA: 1.95",
        "2nd Semester, Year, 2025-2026", "LATER COURSE",
    ])

    def test_restores_boundary_and_summary_without_changing_courses(self):
        fixed = recover_semester_headings(self.primary, [self.reference], "en")
        before = parse_courses(self.primary.splitlines(), "en", False)
        after = parse_courses(fixed.splitlines(), "en", False)
        self.assertEqual([(s['year'], s['sem_num']) for s in after], [(2567, 2), (2568, 1), (2568, 2)])
        self.assertEqual([r for s in before for r in s['subject']], [r for s in after for r in s['subject']])
        self.assertEqual(after[0]['GPA'], '1.88')
        self.assertEqual(after[1]['GPA'], '1.95')

    def test_existing_heading_is_not_duplicated(self):
        fixed = recover_semester_headings(self.primary, [self.reference], "en")
        self.assertEqual(recover_semester_headings(fixed, [self.reference], "en"), fixed)

    def test_single_matching_title_is_insufficient(self):
        reference = self.reference.replace('FUNDAMENTAL WEB PROGRAMMING', 'OTHER COURSE TITLE')
        self.assertEqual(recover_semester_headings(self.primary, [reference], 'en'), self.primary)

    def test_neighboring_semesters_must_match(self):
        reference = self.reference.replace('2024-2025', '2023-2024')
        self.assertEqual(recover_semester_headings(self.primary, [reference], 'en'), self.primary)

    def test_conflicting_years_do_not_trigger_recovery(self):
        conflict = self.reference.replace('1st Semester, Year, 2025-2026', '1st Semester, Year, 2027-2028')
        self.assertEqual(recover_semester_headings(self.primary, [self.reference, conflict], 'en'), self.primary)

    def test_no_reference_never_infers_missing_term(self):
        self.assertEqual(recover_semester_headings(self.primary, [], 'en'), self.primary)


if __name__ == '__main__':
    unittest.main()
