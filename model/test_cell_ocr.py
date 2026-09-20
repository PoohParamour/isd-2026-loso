import unittest

from model.cell_ocr import repair_course_lines


class RepairCourseLinesTests(unittest.TestCase):
    def test_repairs_incomplete_row(self):
        original = "06026240 Intelligent Systems"
        repaired = repair_course_lines(original, {"06026240": "06026240 Intelligent Systems 3 A"})
        self.assertEqual(repaired, "06026240 Intelligent Systems 3 A")

    def test_keeps_already_structured_row(self):
        original = "06026240 Intelligent Systems 3 A"
        repaired = repair_course_lines(original, {"06026240": "06026240 Wrong Name 3 B"})
        self.assertEqual(repaired, original)

    def test_does_not_inject_absent_course(self):
        original = "1st Semester, 2026"
        repaired = repair_course_lines(original, {"06026240": "06026240 Intelligent Systems 3 A"})
        self.assertEqual(repaired, original)

    def test_combines_whole_row_title_with_constrained_cells(self):
        original = "05208101 สัมมนาปริญญาเอก 1 Cr 1 ธ"
        cells = {"05208101": "05208101 จ ม ม น า ป ร ิ ญ ญ า เอ ก 1 Cr 1 S"}
        self.assertEqual(repair_course_lines(original, cells), "05208101 สัมมนาปริญญาเอก 1 Cr 1 S")


if __name__ == "__main__":
    unittest.main()
