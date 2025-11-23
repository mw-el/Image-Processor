from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QSplitter
from PySide6.QtCore import Signal, Qt, QTimer

from .file_tree import FileTreeView
from .thumbnail_grid import ThumbnailGridView

# Delay before loading thumbnails (ms) - prevents lag while navigating
THUMBNAIL_LOAD_DELAY_MS = 3000


class FileBrowserSidebar(QWidget):
    """
    File browser sidebar combining directory tree and thumbnail grid.

    Separation of Concerns: Composite widget, orchestrates FileTree + ThumbnailGrid.
    KISS: Simple vertical layout with splitter.
    """

    # Signal when image is selected from thumbnail grid
    image_selected = Signal(Path)

    def __init__(self, parent=None, start_path: Optional[Path] = None) -> None:
        super().__init__(parent)

        # Pending directory for delayed thumbnail loading
        self._pending_directory: Optional[Path] = None
        self._thumbnail_timer = QTimer(self)
        self._thumbnail_timer.setSingleShot(True)
        self._thumbnail_timer.timeout.connect(self._load_pending_thumbnails)

        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Splitter for tree and grid
        splitter = QSplitter(Qt.Vertical)

        # Directory tree (top)
        tree_container = QWidget()
        tree_layout = QVBoxLayout(tree_container)
        tree_layout.setContentsMargins(4, 4, 4, 4)
        tree_layout.setSpacing(2)

        tree_label = QLabel("<b>Verzeichnisse</b>")
        tree_layout.addWidget(tree_label)

        self.file_tree = FileTreeView(start_path=start_path)
        tree_layout.addWidget(self.file_tree)

        # Thumbnail grid (bottom)
        grid_container = QWidget()
        grid_layout = QVBoxLayout(grid_container)
        grid_layout.setContentsMargins(4, 4, 4, 4)
        grid_layout.setSpacing(2)

        self.grid_label = QLabel("<b>Keine Auswahl</b>")
        grid_layout.addWidget(self.grid_label)

        self.thumbnail_grid = ThumbnailGridView()
        grid_layout.addWidget(self.thumbnail_grid)

        # Add to splitter
        splitter.addWidget(tree_container)
        splitter.addWidget(grid_container)
        splitter.setStretchFactor(0, 1)  # Tree gets 1/3
        splitter.setStretchFactor(1, 2)  # Grid gets 2/3

        layout.addWidget(splitter)

        # Connect signals
        self.file_tree.directory_selected.connect(self._on_directory_selected)
        self.thumbnail_grid.image_selected.connect(self.image_selected.emit)

        # Set fixed width for sidebar
        self.setMinimumWidth(280)
        self.setMaximumWidth(400)

    def _on_directory_selected(self, directory: Path) -> None:
        """Handle directory selection from tree with delayed thumbnail loading."""
        # Update label immediately
        self.grid_label.setText(f"<b>{directory.name}</b>")

        # Clear current thumbnails immediately
        self.thumbnail_grid.clear()

        # Store pending directory and restart timer
        self._pending_directory = directory
        self._thumbnail_timer.stop()
        self._thumbnail_timer.start(THUMBNAIL_LOAD_DELAY_MS)

    def _load_pending_thumbnails(self) -> None:
        """Load thumbnails after delay."""
        if self._pending_directory:
            self.thumbnail_grid.load_directory(self._pending_directory)
            self._pending_directory = None
