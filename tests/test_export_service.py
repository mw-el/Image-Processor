import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core.export_service import ExportService  # noqa: E402


def _make_variant(size=(50, 50), color=(200, 160, 90)):
    return Image.new("RGB", size, color)


class ExportServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.base_path = self.tmp_dir / "sample.jpg"
        self.base_path.write_bytes(b"dummy")
        self.service = ExportService()
        self.variants = {
            "max": _make_variant((1200, 600)),
            "960": _make_variant((960, 480)),
            "480": _make_variant((480, 240)),
        }

    def tearDown(self) -> None:
        for file in self.tmp_dir.glob("*"):
            file.unlink()
        self.tmp_dir.rmdir()

    def test_export_creates_expected_files(self) -> None:
        paths = self.service.export_variants(self.base_path, self.variants)
        expected = {"__sample.webp", "_sample.webp", "sample.webp"}
        self.assertEqual({p.name for p in paths}, expected)
        for name in expected:
            self.assertTrue((self.tmp_dir / name).exists())


if __name__ == "__main__":
    unittest.main()
