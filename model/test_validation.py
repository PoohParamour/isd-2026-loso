import unittest

from model.extract import detect_format, parse_courses, parse_footer, parse_header, parse_summary, parse_term, text_is_usable
from model.validate import validate_record


class ValidateRecordTests(unittest.TestCase):
    def test_course_after_detached_digit_on_continuation_line(self):
        rows = parse_courses([
            "90642999 CHARM SCHOOL 3 s",
            "7 90644007 FOUNDATION ENGLISH 1 3 s",
        ], "en", False)[0]["subject"]
        self.assertEqual([(r["subject_id"], r["subject_name"], r["credit"], r["grade_earn"]) for r in rows], [
            ("90642999", "CHARM SCHOOL", 3, "s"),
            ("90644007", "FOUNDATION ENGLISH 1", 3, "s"),
        ])

    def test_wrapped_title_before_next_course_on_same_line(self):
        rows = parse_courses([
            "06026204 INTRODUCTION TO NETWORKS AND 3 B+",
            "CYBERSECURITY 90644007 FOUNDATION ENGLISH 1 3 S",
        ], "en", False)[0]["subject"]
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["subject_name"], "INTRODUCTION TO NETWORKS AND CYBERSECURITY")
        self.assertEqual(rows[0]["grade_earn"], "b+")
        self.assertEqual(rows[1]["grade_earn"], "s")

    def test_continuation_reference_without_cells_is_not_new_course(self):
        rows = parse_courses(["06026204 NETWORKS 3 B+", "REFERENCE 12345678 STANDARD"], "en", False)[0]["subject"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["subject_name"], "NETWORKS REFERENCE 12345678 STANDARD")

    def test_continuation_can_contain_two_following_courses(self):
        rows = parse_courses([
            "90642999 CHARM SCHOOL 3 S",
            "7 90644007 FOUNDATION ENGLISH 1 3 S 90644008 FOUNDATION ENGLISH 2 3 A",
        ], "en", False)[0]["subject"]
        self.assertEqual([r["subject_id"] for r in rows], ["90642999", "90644007", "90644008"])
        self.assertEqual([r["grade_earn"] for r in rows], ["s", "s", "a"])

    def test_joined_photo_rows_keep_their_own_grades(self):
        rows = parse_courses([
            "1st Semester, 2024",
            "06066303 PROBLEM SOLVING AND COMPUTER PROGRAMMING 3 C . "
            "9064299 CHARM SCHOOL 3 7 90644007 FOUNDATION ENGLISH 1 3 s",
        ], "en", False)[0]["subject"]
        self.assertEqual([(r["subject_id"], r["subject_name"], r["credit"], r["grade_earn"]) for r in rows], [
            ("06066303", "PROBLEM SOLVING AND COMPUTER PROGRAMMING", 3, "c"),
            ("9064299", "CHARM SCHOOL", 3, None),
            ("90644007", "FOUNDATION ENGLISH 1", 3, "s"),
        ])
        validation = validate_record({"transcript_detail": {"semesters": [{"sem_num": 1, "subject": rows}]}})
        self.assertTrue(any(i["code"] == "invalid_subject_id" for i in validation["issues"]))

    def test_joined_row_does_not_borrow_next_course_grade(self):
        rows = parse_courses([
            "06066303 PROBLEM SOLVING AND COMPUTER PROGRAMMING . 90644007 FOUNDATION ENGLISH 1 3 S",
        ], "en", False)[0]["subject"]
        self.assertEqual(len(rows), 2)
        self.assertIsNone(rows[0]["credit"])
        self.assertIsNone(rows[0]["grade_earn"])
        self.assertEqual(rows[1]["grade_earn"], "s")

    def test_prefixed_damaged_row_is_not_title_continuation(self):
        rows = parse_courses([
            "06066303 PROBLEM SOLVING 3 C",
            ". 9064299 CHARM SCHOOL 3 7",
            "| 90644007 FOUNDATION ENGLISH 1 3 S",
        ], "en", False)[0]["subject"]
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["subject_name"], "PROBLEM SOLVING")
        self.assertEqual(rows[1]["subject_name"], "CHARM SCHOOL")

    def test_joined_thai_graduate_rows_keep_type_credit_grade(self):
        rows = parse_courses(["10017081 สัมมนา Nc 1 S 10017100 วิธีวิจัย Cr 3 A"], "th", True)[0]["subject"]
        self.assertEqual([(r["subject_name"], r["type"], r["credit"], r["grade_earn"]) for r in rows],
                         [("สัมมนา", "nc", 1, "s"), ("วิธีวิจัย", "cr", 3, "a")])

    def test_wrapped_course_name_still_preserved(self):
        rows = parse_courses(["06026204 INTRODUCTION TO NETWORKS AND 3 B+", "CYBERSECURITY"], "en", False)[0]["subject"]
        self.assertEqual(rows[0]["subject_name"], "INTRODUCTION TO NETWORKS AND CYBERSECURITY")

    def test_detached_cells_do_not_pollute_title_or_overwrite_grade(self):
        rows = parse_courses(["06026204 NETWORKS 3 B+", "3 C", "3"], "en", False)[0]["subject"]
        self.assertEqual(rows[0]["subject_name"], "NETWORKS")
        self.assertEqual(rows[0]["grade_earn"], "b+")

    def test_numbered_pending_course_keeps_title_number(self):
        rows = parse_courses(["06026200 CALCULUS 1 3"], "en", False)[0]["subject"]
        self.assertEqual((rows[0]["subject_name"], rows[0]["credit"], rows[0]["grade_earn"]), ("CALCULUS 1", 3, None))

    def test_unofficial_photo_heading_preserves_new_semester(self):
        rows = parse_courses(["3rd Semester, Year, 2025-2026",
                              "90643023 TECHNOPRENEURS 3 B+",
                              "151 Semester, Year, 2026-2027",
                              "06026240 INTELLIGENT SYSTEM DEVELOPMENT 3"], "en", False)
        self.assertEqual([(item["year"], item["sem_num"]) for item in rows],
                         [(2568, 3), (2569, 1)])

    def test_english_header_outweighs_thai_ocr_noise(self):
        text = "Name Mr. Example\nDate of Birth January 9, 2005\nDegree Bachelor of Science\nProgram Data Science\n" + "ก" * 35
        self.assertEqual(detect_format(text), "bachelor_en")

    def test_unofficial_header_does_not_invent_university(self):
        header = parse_header(["( Unofficial Transcript )", "Name Mr. Example Student ID 67070127"], "en")
        self.assertIsNone(header["uni_name"])
        self.assertIsNone(header["uni_address"])

    def test_visible_photo_row_keeps_only_readable_fields(self):
        rows = parse_courses(["1st Semester, Year, 2024-2025",
                              "06066303 PROBLEM SOLVING AND COMPUTER PROGRAMMING 3 Cc &"], "en", False)
        self.assertEqual(rows[0]["subject"][0]["subject_id"], "06066303")
        self.assertIsNone(rows[0]["subject"][0]["grade_earn"])

    def test_student_id_can_be_on_separate_line(self):
        header = parse_header(["Student Name: Jane Example", "Registration No: 12345678", "Faculty of Engineering"], "en")
        self.assertEqual(header["student_id"], "12345678")
        self.assertEqual(header["name"], "Jane Example")
        self.assertEqual(header["faculty_name"], "Faculty of Engineering")

    def test_alternate_semester_headings(self):
        self.assertEqual(parse_term("ปีการศึกษา 2567 ภาคเรียนที่ 2", "th"), (2, 2567))
        self.assertEqual(parse_term("ภาคการศึกษาทิ 2 ปีการศึกษา 2565", "th"), (2, 2565))
        self.assertEqual(parse_term("Academic Year 2024 Semester 1", "en"), (1, 2567))
        self.assertEqual(parse_term("1st Semester, Year, 2024-2025", "en"), (1, 2567))
        self.assertEqual(parse_term("1st Semester, Y ear, 2024-2025", "en"), (1, 2567))
        self.assertEqual(parse_term("1st Semester, ¥ ear, 2025-2026", "en"), (1, 2568))
        self.assertEqual(parse_term("2nd Semester , 2022", "en"), (2, 2565))
        self.assertEqual(parse_term("2nd Semester. 2021", "en"), (2, 2564))
        self.assertEqual(parse_term("1st Semester , 2024", "en"), (1, 2567))

    def test_english_graduate_ocr_type_and_credit_glyphs(self):
        rows = parse_courses(
            ["1st Semester , 2022", "10017081 SEMINAR 1 Ne I S", "10017100 RESEARCH METHODS Ne 3 S"],
            "en",
            True,
        )
        self.assertEqual([(item["subject_id"], item["type"], item["credit"]) for item in rows[0]["subject"]],
                         [("10017081", "nc", 1), ("10017100", "nc", 3)])

    def test_unofficial_transcript_text_layer_is_usable(self):
        text = "( Unofficial Transcript )\nStudent ID: 67070124\n" + ("course text " * 40)
        self.assertTrue(text_is_usable(text))

    def test_pending_english_courses_are_preserved(self):
        rows = parse_courses(
            ["1st Semester, Year, 2024-2025", "06026211 DATA STRUCTURE 3"],
            "en",
            False,
        )
        self.assertEqual(rows[0]["year"], 2567)
        self.assertEqual(rows[0]["subject"][0]["subject_id"], "06026211")
        self.assertIsNone(rows[0]["subject"][0]["grade_earn"])

    def test_unreadable_grade_keeps_visible_course_without_guessing(self):
        rows = parse_courses(
            [
                "ภาคการศึกษาที่ 1 ปีการศึกษา 2561",
                "02366051 ประวัติศาสตร์ศิลปะและการออกแบบ 3 =",
                "90591002 กีฬาและนันทนาการ 1 Z",
            ],
            "th",
            False,
        )
        subjects = rows[0]["subject"]
        self.assertEqual([item["subject_id"] for item in subjects], ["02366051", "90591002"])
        self.assertEqual([item["credit"] for item in subjects], [3, 1])
        self.assertEqual([item["grade_earn"] for item in subjects], [None, None])

    def test_unreadable_credit_keeps_visible_graduate_course(self):
        rows = parse_courses(
            ["2nd Semester. 2021", "14097102 STRATEGIC OPERATIONS MANAGEMENT Cr al B+"],
            "en",
            True,
        )
        subject = rows[0]["subject"][0]
        self.assertEqual((subject["subject_id"], subject["type"], subject["grade_earn"]),
                         ("14097102", "cr", "b+"))
        self.assertIsNone(subject["credit"])

    def test_unofficial_summary_and_issued_date_labels(self):
        summary = parse_summary(["Total number of credit earned 78"], "en")
        footer = parse_footer(["Date Issued: September 20, 2026"], "en")
        self.assertEqual(summary["total_credits_earned"], 78)
        self.assertEqual(footer["updated_at"], "2026-09-20")

    def test_course_named_school_is_not_a_faculty(self):
        header = parse_header(["90642999 CHARM SCHOOL 3 5", "Student ID: 67070124"], "en")
        self.assertIsNone(header["faculty_name"])

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

    def test_thai_course_column_glyph_confusions_are_position_bound(self):
        rows = parse_courses(
            [
                "ภาคการศึกษาที่ 1 ปีการศึกษา 2564",
                "90401012 ความรู้เบื้องต้นทางการตลาด 3 ๐",
                "90307001 ภาษาไทยเพื่อการสื่อสาร 3 8+",
            ],
            "th",
            False,
        )
        self.assertEqual([item["grade_earn"] for item in rows[0]["subject"]], ["c", "b+"])

    def test_thai_graduate_type_and_grade_glyph_confusions(self):
        rows = parse_courses(
            [
                "ภาคการศึกษาที่ 1 ปีการศึกษา 2565",
                "03258902 ดุษฎีนิพนธ์ ๓ | 12 | ร",
                "03258902 ดุษฎีนิพนธ์ Cr | 12 | 1!",
                "03258902 ดุษฎีนิพนธ์ Cr 12 8",
                "03258902 ดุษฎีนิพนธ์ Cr 12 |",
            ],
            "th",
            True,
        )
        self.assertEqual(rows[0]["subject"][0]["type"], "cr")
        self.assertEqual(rows[0]["subject"][0]["grade_earn"], "s")
        self.assertEqual(rows[0]["subject"][1]["grade_earn"], "i")
        self.assertEqual(rows[0]["subject"][2]["grade_earn"], "s")
        self.assertEqual(rows[0]["subject"][3]["grade_earn"], "i")

    def test_footer_is_not_appended_to_wrapped_course_name(self):
        rows = parse_courses(
            ["1st Semester, 2024", "06026240 INTELLIGENT SYSTEM 3 A", "Date of Issued: January 17, 2025"],
            "en",
            False,
        )
        self.assertEqual(rows[0]["subject"][0]["subject_name"], "INTELLIGENT SYSTEM")

    def test_missing_decimal_in_labeled_gps_is_repaired(self):
        rows = parse_courses(["1st Semester, 2022", "GPS : 338 GPA : 3.34"], "en", False)
        self.assertEqual(rows[0]["GPS"], "3.38")
        self.assertEqual(rows[0]["GPA"], "3.34")

    def test_thai_summary_label_and_leading_table_border_gpa(self):
        rows = parse_courses(
            [
                "ภาคการศึกษาที่ 1 ปีการศึกษา 2564",
                "ะแนนเฉลี่ยประจําภาคการศึกษา : 0.82 คะแนนเฉลี่ย 12.34",
            ],
            "th",
            False,
        )
        self.assertEqual(rows[0]["GPS"], "0.82")
        self.assertEqual(rows[0]["GPA"], "2.34")

    def test_thai_damaged_summary_and_header_marks(self):
        summary = parse_summary(
            ["สอบประมวลความรู : ผาน", "จํานวนหนวยกิตทีสอบไดทั้งหมด : 40", "คะแนนเฉลิยสะสม : 3.86"],
            "th",
        )
        header = parse_header(["วันทิสําเร็จการศึกษา 25 มิถุนายน 2567"], "th")
        self.assertEqual(summary["master_comprehensive"], "ผ่าน")
        self.assertEqual(summary["total_credits_earned"], 40)
        self.assertEqual(summary["cumulative_gpa"], "3.86")
        self.assertEqual(header["grad_date"], "2024-06-25")

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

    def test_pending_course_without_grade_is_valid(self):
        record = {
            "header_detail": {"student_id": "67070124", "name": "Test", "faculty_name": "IT", "program": "DSBA"},
            "transcript_detail": {
                "semesters": [
                    {
                        "year": 2569,
                        "sem_num": 1,
                        "subject": [{"subject_id": "06026211", "credit": 3, "grade_earn": None}],
                    }
                ]
            },
        }
        result = validate_record(record)
        self.assertFalse(result["needs_review"])
        self.assertEqual(result["course_count"], 1)


if __name__ == "__main__":
    unittest.main()
