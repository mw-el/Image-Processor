import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core.image_store import ImageStore, ImageState  # noqa: E402


class ImageStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = ImageStore()
        self.path = Path("/tmp/test.jpg")
        self.store.load(self.path)

    def test_push_and_undo_redo(self) -> None:
        first_state = ImageState(path=self.path, description="Step 1", payload={"value": 1})
        self.store.push_state(first_state)
        second_state = ImageState(path=self.path, description="Step 2", payload={"value": 2})
        self.store.push_state(second_state)

        undone = self.store.undo()
        self.assertEqual(undone.description, "Step 1")
        redone = self.store.redo()
        self.assertEqual(redone.description, "Step 2")

    def test_reset_to_original_clears_history(self) -> None:
        self.store.push_state(ImageState(path=self.path, description="Step", payload={} ))
        self.assertTrue(self.store.reset_to_original())
        self.assertFalse(self.store.undo_stack)
        self.assertFalse(self.store.redo_stack)


if __name__ == "__main__":
    unittest.main()
