import sys
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core.crop_geometry import CropGeometry  # noqa: E402
from core.outpainting_prepare import build_canvas_and_mask  # noqa: E402


class CropGeometryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original = Image.new("RGB", (400, 300), (100, 120, 140))

    def test_whitespace_detection(self) -> None:
        geometry = CropGeometry(
            selection=(0.0, 0.0, 200.0, 150.0),
            image_bounds=(20.0, 20.0, 160.0, 120.0),
            scale=0.5,
        )
        self.assertTrue(geometry.has_whitespace())

    def test_build_canvas_and_mask_copies_overlap(self) -> None:
        geometry = CropGeometry(
            selection=(0.0, 0.0, 200.0, 150.0),
            image_bounds=(0.0, 0.0, 200.0, 150.0),
            scale=1.0,
        )
        canvas, mask = build_canvas_and_mask(self.original, geometry)
        self.assertEqual(canvas.size, (200, 150))
        self.assertEqual(mask.size, (200, 150))
        self.assertEqual(canvas.getpixel((10, 10)), (100, 120, 140))
        self.assertEqual(mask.getpixel((10, 10)), 0)


if __name__ == "__main__":
    unittest.main()

