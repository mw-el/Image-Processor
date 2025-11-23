from __future__ import annotations

from pathlib import Path
from typing import Optional, Set
import subprocess

from PySide6.QtWidgets import QListWidget, QListWidgetItem, QApplication, QMenu
from PySide6.QtCore import Signal, Qt, QThread, QObject, QSize
from PySide6.QtGui import QPixmap, QIcon, QAction

from ...core.thumbnail_cache import ThumbnailCache
from ...core.image_metadata import extract_image_metadata

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif"}


class ThumbnailLoader(QObject):
    """Background thread worker for thumbnail generation."""
    thumbnail_ready = Signal(Path, QPixmap)

    def __init__(self, cache: ThumbnailCache) -> None:
        super().__init__()
        self.cache = cache

    def load_thumbnail(self, image_path: Path) -> None:
        """Load or generate thumbnail in background."""
        try:
            # Get or create thumbnail
            thumb_path = self.cache.get_or_create_thumbnail(image_path)

            if thumb_path and thumb_path.exists():
                # Load pixmap
                pixmap = QPixmap(str(thumb_path))
                if not pixmap.isNull():
                    self.thumbnail_ready.emit(image_path, pixmap)

        except Exception:
            # Fail Fast: Silently skip failed thumbnails
            pass


class ThumbnailGridView(QListWidget):
    """
    Grid view showing image thumbnails from selected directory.

    Separation of Concerns: UI only, uses ThumbnailCache for logic.
    KISS: QListWidget in IconMode, simple lazy loading.
    """

    # Signal when image is clicked
    image_selected = Signal(Path)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.cache = ThumbnailCache()
        self.current_directory: Optional[Path] = None
        self._image_paths: dict[str, Path] = {}  # Item text -> Path mapping

        # Setup grid view
        self.setViewMode(QListWidget.IconMode)
        self.setIconSize(QSize(256, 256))
        self.setResizeMode(QListWidget.Adjust)
        self.setSpacing(10)
        self.setMovement(QListWidget.Static)
        self.setWrapping(True)

        # Enable tooltips
        self.setMouseTracking(True)

        # Connect signals
        self.itemClicked.connect(self._on_item_clicked)

    def load_directory(self, directory: Path) -> None:
        """
        Load all images from directory and display thumbnails.

        KISS: Simple synchronous loading (can optimize with threading later).
        """
        # Fail Fast: Validate
        if not directory.exists() or not directory.is_dir():
            return

        self.current_directory = directory
        self.clear()
        self._image_paths.clear()

        # Find all image files
        image_files = []
        for ext in SUPPORTED_EXTENSIONS:
            image_files.extend(directory.glob(f"*{ext}"))
            image_files.extend(directory.glob(f"*{ext.upper()}"))

        # Sort by name
        image_files.sort(key=lambda p: p.name.lower())

        # Add items
        for image_path in image_files:
            self._add_thumbnail_item(image_path)

    def _add_thumbnail_item(self, image_path: Path) -> None:
        """Add thumbnail item to grid (lazy loading)."""
        # Create item
        item = QListWidgetItem(image_path.name)
        item.setTextAlignment(Qt.AlignCenter)

        # Set tooltip with metadata
        try:
            metadata = extract_image_metadata(image_path)
            item.setToolTip(metadata.to_tooltip_html())
        except Exception:
            # Fallback tooltip
            item.setToolTip(image_path.name)

        # Load thumbnail (sync for now, can async later)
        try:
            thumb_path = self.cache.get_or_create_thumbnail(image_path)
            if thumb_path and thumb_path.exists():
                pixmap = QPixmap(str(thumb_path))
                if not pixmap.isNull():
                    item.setIcon(QIcon(pixmap))
        except Exception:
            # No icon if thumbnail fails
            pass

        # Store mapping
        self._image_paths[image_path.name] = image_path

        # Add to list
        self.addItem(item)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        """Handle thumbnail click."""
        # Get path from mapping
        image_path = self._image_paths.get(item.text())

        if image_path and image_path.exists():
            # Emit signal
            self.image_selected.emit(image_path)

    def contextMenuEvent(self, event) -> None:
        """Handle right-click on thumbnail."""
        # Get item at click position
        item = self.itemAt(event.pos())
        if not item:
            return

        # Get path from mapping
        image_path = self._image_paths.get(item.text())
        if not image_path or not image_path.exists():
            return

        # Create context menu
        menu = QMenu(self)
        show_in_fm_action = QAction("Im Dateimanager anzeigen", self)
        show_in_fm_action.triggered.connect(lambda: self._show_in_file_manager(image_path))
        menu.addAction(show_in_fm_action)

        # Show menu at cursor position
        menu.exec(event.globalPos())

    def _show_in_file_manager(self, image_path: Path) -> None:
        """Open system file manager with image's directory."""
        try:
            # Open parent directory in file manager
            subprocess.Popen(['xdg-open', str(image_path.parent)])
        except Exception:
            # Fail Fast: Silently ignore if file manager can't be opened
            pass
