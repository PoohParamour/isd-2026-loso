import unittest

import cv2
import numpy as np
from PIL import Image

from model.phone_table import line_bands, plausible_gpa_line, ruled_geometry
from model.photo_geometry import straighten_clipped_photo


class PhoneGeometryTests(unittest.TestCase):
    def test_gpa_fallback_requires_all_visible_values_in_range(self):
        self.assertTrue(plausible_gpa_line("GPS : 2.17 GPA 2.17"))
        self.assertTrue(plausible_gpa_line("GPS : - GPA : 2.42"))
        self.assertFalse(plausible_gpa_line("GPS : 2.17 GPA : 31.95"))
        self.assertFalse(plausible_gpa_line("GPS : 2.17 GPA : unreadable"))

    def test_recovers_two_table_columns_with_slanted_rules(self):
        image = np.full((1800, 1400), 235, np.uint8)
        top, bottom = 360, 1620
        for fraction in (0.06, 0.43, 0.467, 0.504, 0.87, 0.907, 0.944):
            x = round(1400 * fraction)
            cv2.line(image, (x + 5, top), (x - 5, bottom), 65, 2)
        cv2.line(image, (84, top), (1322, top + 6), 65, 2)
        cv2.line(image, (74, bottom), (1312, bottom + 6), 65, 2)
        result = ruled_geometry(image)
        self.assertIsNotNone(result)
        _, columns, _ = result
        self.assertEqual(len(columns), 2)
        self.assertLess(abs(columns[0][1] - round(1400 * 0.43)), 15)
        self.assertLess(abs(columns[1][0] - round(1400 * 0.504)), 15)

    def test_blank_or_unruled_image_is_not_a_phone_table(self):
        self.assertIsNone(ruled_geometry(np.full((1800, 1400), 255, np.uint8)))

    def test_clipped_page_uses_visible_lower_table_rule(self):
        canvas = np.full((2800, 2100, 3), 35, np.uint8)
        # Physical bottom edge is beyond the camera frame. Three page edges
        # and the bottom table rule remain visible, with a visible footer.
        quad = np.array([[250, 300], [1850, 320], [2300, 3200], [-50, 3200]], np.int32)
        cv2.fillConvexPoly(canvas, quad, (220, 220, 220))
        cv2.line(canvas, (50, 2480), (2030, 2430), (55, 55, 55), 5)
        result = straighten_clipped_photo(Image.fromarray(canvas))
        self.assertIsNotNone(result)
        self.assertGreater(result.height, 2000)

    def test_full_white_page_does_not_trigger_clipped_photo_fallback(self):
        self.assertIsNone(
            straighten_clipped_photo(Image.new("RGB", (2100, 2800), "white"))
        )

    def test_line_projection_keeps_separate_rows_and_joins_small_glyph_gaps(self):
        ink = np.zeros((90, 120), np.uint8)
        ink[10:15, 10:100] = 255
        ink[17:22, 10:100] = 255
        ink[45:55, 10:100] = 255
        self.assertEqual(line_bands(ink, 10), [(10, 22), (45, 55)])


if __name__ == "__main__":
    unittest.main()
