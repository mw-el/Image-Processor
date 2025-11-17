import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core.export_service import ExportService, ExportVariant  # noqa: E402


def _make_variant(size=(50, 50), color=(200, 160, 90)):
    return Image.new("RGB", size, color)


class ExportServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.base_path = self.tmp_dir / "sample.jpg"
        self.base_path.write_bytes(b"dummy")
        self.service = ExportService()
        self.variants = [
            ExportVariant(prefix="__", resolution=(1200, 600), ratio_suffix="16x9", image=_make_variant((1200, 600))),
            ExportVariant(prefix="_", resolution=(960, 480), ratio_suffix="16x9", image=_make_variant((960, 480))),
            ExportVariant(prefix="", resolution=(480, 240), ratio_suffix="16x9", image=_make_variant((480, 240))),
        ]

    def tearDown(self) -> None:
        for file in self.tmp_dir.glob("*"):
            file.unlink()
        self.tmp_dir.rmdir()

    def test_export_creates_expected_files(self) -> None:
        paths = self.service.export_variants(self.base_path, self.variants)
        expected = {
            "__sample_1200x600_16x9.webp",
            "_sample_960x480_16x9.webp",
            "sample_480x240_16x9.webp",
        }
        self.assertEqual({p.name for p in paths}, expected)
        for name in expected:
            self.assertTrue((self.tmp_dir / name).exists())


if __name__ == "__main__":
    unittest.main()
