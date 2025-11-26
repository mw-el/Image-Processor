import sys
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core.image_resize import resize_for_variant  # noqa: E402


def _create_image(size=(100, 50), color=(50, 120, 200)):
    return Image.new("RGB", size, color)


class _FailUpscaler:
    def upscale_min_size(self, *args, **kwargs):
        raise AssertionError("Upscaler should not have been used for downscale")


class _DummyUpscaler:
    def __init__(self) -> None:
        self.calls: list[tuple[tuple[int, int], int, int]] = []

    def upscale_min_size(self, img: Image.Image, min_w: int, min_h: int) -> Image.Image:
        self.calls.append((img.size, min_w, min_h))
        scale = max(min_w / img.width, min_h / img.height)
        scale = max(1.0, scale)
        new_size = (int(round(img.width * scale)), int(round(img.height * scale)))
        return img.resize(new_size, Image.Resampling.NEAREST)


class ResizeForVariantTests(unittest.TestCase):
    def test_downscale_skips_upscaler(self) -> None:
        img = _create_image(size=(400, 200))
        result = resize_for_variant(img, 200, 100, upscaler=_FailUpscaler())
        self.assertEqual(result.size, (200, 100))

    def test_upscale_invokes_upscaler(self) -> None:
        img = _create_image(size=(100, 50))
        dummy = _DummyUpscaler()
        result = resize_for_variant(img, 400, 200, upscaler=dummy)
        self.assertEqual(result.size, (400, 200))
        self.assertEqual(len(dummy.calls), 1)
        self.assertEqual(dummy.calls[0][1:], (400, 200))


if __name__ == "__main__":
    unittest.main()

