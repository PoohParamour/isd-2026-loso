import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from model.extract import _orient_photo, extract


class OrientationTests(unittest.TestCase):
    def test_rotates_to_strongest_transcript_direction(self):
        for index in (1, 2, 3):
            with self.subTest(index=index), tempfile.TemporaryDirectory() as temp:
                page = Image.new('RGB', (100, 150), 'white')
                page.putpixel((10, 20), (0, 0, 0))
                readings = ['noise'] * 4
                readings[index] = 'Unofficial Transcript Semester 12345678 87654321'
                with patch('model.extract.run', side_effect=readings):
                    result = _orient_photo(page, Path(temp))
                expected = page.rotate(index * 90, expand=True)
                self.assertEqual(result.size, expected.size)
                self.assertEqual(result.tobytes(), expected.tobytes())

    def test_tied_or_weak_evidence_keeps_original(self):
        for readings in (['Semester'] * 4, ['', '12345678', '', ''],
                         ['Semester Course 12345678'] * 4):
            with tempfile.TemporaryDirectory() as temp:
                page = Image.new('RGB', (100, 150))
                with patch('model.extract.run', side_effect=readings):
                    self.assertIs(_orient_photo(page, Path(temp)), page)

    @patch('model.photo_geometry.straighten_photo', return_value=None)
    @patch('model.extract._orient_photo', side_effect=lambda image, work: image.rotate(90, expand=True))
    @patch('model.extract.read_image_profile', return_value=('Student ID 12345678', '1st Semester, 2024\n12345678 EXAMPLE COURSE 3 A'))
    @patch('model.extract.read_document', return_value=('Student ID 12345678', 'tesseract'))
    def test_borderless_image_gets_oriented_once(self, document, profile, orient, geometry):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'white.png'
            Image.new('RGB', (200, 100), 'white').save(path)
            result = extract(path, format_id='bachelor_en', image_layout='profile')
        self.assertEqual(result['validation']['course_count'], 1)
        orient.assert_called_once()
        geometry.assert_called_once()


if __name__ == '__main__':
    unittest.main()
