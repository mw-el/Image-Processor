from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ImageState:
    """Tracks a single state snapshot for undo/redo."""

    path: Path
    description: str = ""
    payload: Optional[object] = None  # placeholder for actual image object


@dataclass
class ImageStore:
    """
    Central place for original/current image references and history handling.
    Actual pixel data is deferred to future implementation.
    """

    original: Optional[ImageState] = None
    current: Optional[ImageState] = None
    undo_stack: list[ImageState] = field(default_factory=list)
    redo_stack: list[ImageState] = field(default_factory=list)

    def load(self, image_path: Path) -> None:
        self.original = ImageState(path=image_path, description="Original geladen")
        self.current = self.original
        self.undo_stack.clear()
        self.redo_stack.clear()

    def push_state(self, state: ImageState) -> None:
        if self.current:
            self.undo_stack.append(self.current)
        self.current = state
        self.redo_stack.clear()

    def undo(self) -> Optional[ImageState]:
        if not self.undo_stack:
            return None
        if self.current:
            self.redo_stack.append(self.current)
        self.current = self.undo_stack.pop()
        return self.current

    def redo(self) -> Optional[ImageState]:
        if not self.redo_stack:
            return None
        if self.current:
            self.undo_stack.append(self.current)
        self.current = self.redo_stack.pop()
        return self.current

    def reset_to_original(self) -> Optional[ImageState]:
        if not self.original:
            return None
        self.current = self.original
        self.undo_stack.clear()
        self.redo_stack.clear()
        return self.current

    def has_history(self) -> bool:
        return bool(self.undo_stack or self.redo_stack)

    def has_unsaved_changes(self) -> bool:
        return bool(self.undo_stack)
