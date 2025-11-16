import sys
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core.image_processing import ProcessingPipeline  # noqa: E402


def _create_sample_image(color=(120, 180, 200)):
    img = Image.new("RGB", (200, 100), color)
    return img


class ProcessingPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pipeline = ProcessingPipeline()
        self.image = _create_sample_image()

    def test_resize_preserves_target_width(self) -> None:
        result = self.pipeline.resize_with_quality(self.image, target_width=100)
        self.assertEqual(result.width, 100)
        self.assertTrue(abs(result.height - 50) <= 1)

    def test_generate_variants_returns_requested_widths(self) -> None:
        variants = self.pipeline.generate_variants(self.image, [150, 75])
        widths = {variant.width for variant in variants}
        self.assertEqual(widths, {150, 75})


if __name__ == "__main__":
    unittest.main()
