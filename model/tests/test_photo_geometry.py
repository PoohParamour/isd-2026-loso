import unittest

import cv2
import numpy as np
from PIL import Image

from model.photo_geometry import _page_quad, _ordered, straighten_photo


class PhotoGeometryTests(unittest.TestCase):
    def test_upright_page_is_cropped_even_without_tilt(self):
        canvas = np.full((1800, 1400, 3), 35, np.uint8)
        cv2.rectangle(canvas, (180, 180), (1220, 1640), (200, 200, 200), -1)
        result = straighten_photo(Image.fromarray(canvas))
        self.assertIsNotNone(result)
        self.assertLess(result.width, 1100)
        self.assertGreater(result.height, 1400)

    def test_clipped_frame_corners_are_not_used_as_page_corners(self):
        canvas = np.full((2000, 1200, 3), 35, np.uint8)
        expected = np.array([[-100, 120], [1350, 100], [1120, 1840], [130, 1820]], np.float32)
        cv2.fillConvexPoly(canvas, expected.astype(np.int32), (180, 180, 180))
        quad = _page_quad(canvas)
        self.assertIsNotNone(quad)
        np.testing.assert_allclose(_ordered(quad), expected, atol=20)

    def test_full_white_scan_does_not_get_photo_cropping(self):
        self.assertIsNone(straighten_photo(Image.new('RGB', (1400, 1800), 'white')))

    def test_strongly_rotated_page_retains_quadrilateral_fallback(self):
        canvas = Image.new('RGB', (1400, 1600), (35,35,35))
        canvas.paste(Image.new('RGB', (1200,1400), 'white'), (100,100))
        rotated = canvas.rotate(40,expand=True,fillcolor=(35,35,35))
        self.assertIsNotNone(straighten_photo(rotated))


if __name__ == '__main__':
    unittest.main()
