import unittest

from backend.app.main import is_heif


def heif_header(major_brand: bytes, compatible_brands: tuple[bytes, ...] = ()) -> bytes:
    payload = major_brand + b"\x00\x00\x00\x00" + b"".join(compatible_brands)
    return (8 + len(payload)).to_bytes(4, "big") + b"ftyp" + payload


class HeifValidationTest(unittest.TestCase):
    def test_accepts_heic_major_brand(self) -> None:
        self.assertTrue(is_heif(heif_header(b"heic")))

    def test_accepts_heif_compatible_brand(self) -> None:
        self.assertTrue(is_heif(heif_header(b"isom", (b"mif1",))))

    def test_rejects_non_heif_isobmff_file(self) -> None:
        self.assertFalse(is_heif(heif_header(b"isom", (b"mp42",))))

    def test_rejects_truncated_file(self) -> None:
        self.assertFalse(is_heif(b"\x00\x00\x00\x18ftypheic"))


if __name__ == "__main__":
    unittest.main()
