import unittest

from PIL import Image

from src.core.image_session import ImageSession
from src.core.settings import load_settings


class ImageSessionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = load_settings()
        self.session = ImageSession(self.settings)

    def _dummy_image(self, size=(1200, 800)) -> Image.Image:
        return Image.new("RGB", size, color="white")

    def test_build_variant_specs_for_default_rules(self) -> None:
        image = self._dummy_image((1500, 1000))
        self.session.set_ratio("3:2", 3 / 2, None)

        specs, suffix = self.session.build_variant_specs(image)

        self.assertEqual(suffix, "3x2")
        self.assertEqual(
            specs,
            [
                ("__", 1500, 1000),
                ("_", 960, 640),
                ("", 480, 320),
            ],
        )

    def test_variant_rules_for_16_9_overrides_default(self) -> None:
        image = self._dummy_image((4000, 3000))
        self.session.set_ratio("16:9", 16 / 9, None)

        specs, suffix = self.session.build_variant_specs(image)

        self.assertEqual(suffix, "16x9")
        self.assertEqual(
            specs,
            [
                ("__", 3840, 2160),
                ("_", 1920, 1080),
                ("", 1280, 720),
            ],
        )

    def test_ratio_derived_when_not_selected(self) -> None:
        image = self._dummy_image((1024, 768))
        specs, suffix = self.session.build_variant_specs(image)

        self.assertEqual(suffix, "4x3")
        self.assertEqual(
            specs,
            [
                ("__", 1024, 768),
                ("_", 960, 720),
                ("", 480, 360),
            ],
        )


if __name__ == "__main__":
    unittest.main()
