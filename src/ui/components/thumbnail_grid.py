from __future__ import annotations

from pathlib import Path
from typing import Optional, Set
import subprocess

from PySide6.QtWidgets import QListWidget, QListWidgetItem, QApplication, QMenu
from PySide6.QtCore import Signal, Qt, QThread, QObject, QSize, QRect, QRectF, QTimer
from PySide6.QtGui import QPixmap, QIcon, QAction

from ...core.thumbnail_cache import ThumbnailCache
from ...core.image_metadata import extract_image_metadata
from .magnifier_widget import MagnifierWidget
from PIL import Image

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif"}
COMFY_START_SCRIPT = Path.home() / "_AA_ComfyUI" / "start-gui.sh"


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
    magnifier_started = Signal()
    magnifier_stopped = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        # Sort mode: "name", "date", "resolution"
        self.sort_mode = "date"

        self.cache = ThumbnailCache()
        self.current_directory: Optional[Path] = None
        self._item_paths: dict[int, Path] = {}  # Map item index to Path
        self._loading_threads: list[QThread] = []

        # Setup grid view (4x3-ish cells, responsive)
        self.cell_size = QSize(260, 200)
        self.setViewMode(QListWidget.IconMode)
        self.setIconSize(self.cell_size)
        self.setResizeMode(QListWidget.Adjust)
        self.setSpacing(12)
        self.setMovement(QListWidget.Static)
        self.setWrapping(True)
        self.setUniformItemSizes(True)
        self.setGridSize(QSize(self.cell_size.width() + 12, self.cell_size.height() + 32))
        self.setWordWrap(True)
        self.setStyleSheet("QListWidget { background: #f9f9f9; }")

        # Enable tooltips
        self.setMouseTracking(True)

        # Magnifier widget
        self.magnifier = MagnifierWidget(self, size=150)
        self._magnifier_timer: Optional[int] = None
        self._pending_item = None
        self._pending_pos = None
        self._magnifier_active = False
        self._active_item = None

        # Connect signals
        self.itemClicked.connect(self._on_item_clicked)

    def load_directory(self, directory: Path) -> int:
        """
        Load all images from directory and display thumbnails.

        KISS: Simple synchronous loading (no cache).
        """
        if not directory.exists() or not directory.is_dir():
            return 0

        self.current_directory = directory
        self.clear()
        self._item_paths.clear()

        # Collect all image files by explicit extension search
        all_images: list[Path] = []
        for ext in SUPPORTED_EXTENSIONS:
            try:
                all_images.extend(directory.glob(f"*{ext}"))
                all_images.extend(directory.glob(f"*{ext.upper()}"))
            except Exception:
                pass

        # Deduplicate and sort according to current sort mode
        all_images = list(set(all_images))
        all_images = self._sort_images(all_images)

        count = 0
        for path in all_images:
            try:
                self._add_thumbnail_item(path)
                count += 1
            except Exception:
                pass

        return count

    def _sort_images(self, images: list[Path]) -> list[Path]:
        """Sort images according to current sort mode."""
        if self.sort_mode == "name":
            # A-Z alphabetically
            return sorted(images, key=lambda p: p.name.lower())
        elif self.sort_mode == "date":
            # Newest first (highest mtime first)
            return sorted(images, key=lambda p: p.stat().st_mtime, reverse=True)
        elif self.sort_mode == "resolution":
            # Highest resolution first (width * height)
            def get_resolution(path: Path) -> int:
                try:
                    pixmap = QPixmap(str(path))
                    if not pixmap.isNull():
                        return pixmap.width() * pixmap.height()
                except Exception:
                    pass
                return 0
            return sorted(images, key=get_resolution, reverse=True)
        else:
            # Fallback: alphabetically
            return sorted(images, key=lambda p: p.name.lower())

    def set_sort_mode(self, mode: str) -> None:
        """Change sort mode and reload directory."""
        if mode not in ("name", "date", "resolution"):
            return
        self.sort_mode = mode
        if self.current_directory:
            self.load_directory(self.current_directory)

    def _add_thumbnail_item(self, image_path: Path) -> None:
        """Add thumbnail item to grid (sync load, no cache)."""
        item = QListWidgetItem(image_path.name)
        item.setTextAlignment(Qt.AlignCenter)

        try:
            metadata = extract_image_metadata(image_path)
            item.setToolTip(metadata.to_tooltip_html())
        except Exception:
            item.setToolTip(image_path.name)

        pixmap = None
        try:
            pixmap = QPixmap(str(image_path))
            if not pixmap.isNull():
                pixmap = pixmap.scaled(
                    self.cell_size,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
        except Exception:
            pixmap = None

        if pixmap and not pixmap.isNull():
            item.setIcon(QIcon(pixmap))

        self.addItem(item)
        # Store path using item's current index
        item_index = self.row(item)
        self._item_paths[item_index] = image_path

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        """Handle thumbnail click."""
        image_path = self._path_for_item(item)

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
        image_path = self._path_for_item(item)
        if not image_path or not image_path.exists():
            return

        # Create context menu
        menu = QMenu(self)
        show_in_fm_action = QAction("Im Dateimanager anzeigen", self)
        show_in_fm_action.triggered.connect(lambda: self._show_in_file_manager(image_path))
        menu.addAction(show_in_fm_action)

        if COMFY_START_SCRIPT.exists():
            open_comfy_action = QAction("In ComfyUI laden", self)
            open_comfy_action.triggered.connect(lambda: self._open_in_comfyui(image_path))
            menu.addAction(open_comfy_action)

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

    def _open_in_comfyui(self, image_path: Path) -> None:
        """Launch ComfyUI GUI with the image preloaded (if available)."""
        try:
            subprocess.Popen([str(COMFY_START_SCRIPT), "--load-image", str(image_path)])
        except Exception:
            # Fail fast: do not block UI on launch issues
            pass

    def _path_for_item(self, item: QListWidgetItem) -> Optional[Path]:
        """Return filesystem path for a QListWidgetItem."""
        item_index = self.row(item)
        return self._item_paths.get(item_index)

    def path_for_item(self, item: QListWidgetItem) -> Optional[Path]:
        """Public helper for consumers needing the mapped path."""
        return self._path_for_item(item)

    def selected_paths(self) -> list[Path]:
        """Return list of Paths for the current selection."""
        paths: list[Path] = []
        for item in self.selectedItems():
            path = self._path_for_item(item)
            if path:
                paths.append(path)
        return paths

    def mouseMoveEvent(self, event) -> None:
        """Handle mouse move to show magnifier with 1s delay and then follow cursor."""
        super().mouseMoveEvent(event)

        # Cancel pending timer
        if self._magnifier_timer is not None:
            self.killTimer(self._magnifier_timer)
            self._magnifier_timer = None

        # Get item under cursor
        item = self.itemAt(event.pos())
        if not item:
            self.magnifier.hide()
            self._pending_pos = None
            self._pending_item = None
            self._magnifier_active = False
            self._active_item = None
            return

        # If magnifier already active on this item, update immediately
        if self._magnifier_active and self._active_item is item:
            self._show_magnifier(event.position(), item)
            return

        # Otherwise start delayed activation
        # Start 1000ms timer before showing magnifier
        self._magnifier_timer = self.startTimer(1000)
        self._pending_pos = event.position()
        self._pending_item = item
        self._magnifier_active = False
        self._active_item = None

    def timerEvent(self, event) -> None:
        """Show magnifier after delay."""
        if event.timerId() == self._magnifier_timer:
            self.killTimer(self._magnifier_timer)
            self._magnifier_timer = None
            if self._pending_pos is None or self._pending_item is None:
                self.magnifier.hide()
                self.magnifier_stopped.emit()
                return
            self._show_magnifier(self._pending_pos, self._pending_item)
            self._pending_pos = None
            self._pending_item = None
            self._magnifier_active = True

    def _show_magnifier(self, pos, item) -> None:
        """Actually show the magnifier."""
        # Emit signal FIRST to hide info dialog before magnifier appears
        self.magnifier_started.emit()

        # Get image path
        image_path = self._path_for_item(item)
        if not image_path or not image_path.exists():
            self.magnifier.hide()
            return

        # Get item's visual rectangle
        item_rect = self.visualItemRect(item)

        try:
            # Load original image
            pil_image = Image.open(image_path)

            # Calculate scale: thumbnail fits within item_rect
            scale_x = item_rect.width() / pil_image.width
            scale_y = item_rect.height() / pil_image.height
            scale = min(scale_x, scale_y)

            # Calculate actual displayed image rect (centered in item_rect)
            display_width = pil_image.width * scale
            display_height = pil_image.height * scale
            offset_x = item_rect.x() + (item_rect.width() - display_width) / 2
            offset_y = item_rect.y() + (item_rect.height() - display_height) / 2

            image_rect = QRectF(offset_x, offset_y, display_width, display_height)

            # Update magnifier
            self.magnifier.update_magnifier(
                pos,
                pil_image,
                image_rect,
                scale,
                (self.width(), self.height())
            )
            self._active_item = item

        except Exception:
            # Fail Fast: Hide on error
            self.magnifier.hide()

    def leaveEvent(self, event) -> None:
        """Hide magnifier when mouse leaves widget."""
        if self._magnifier_timer is not None:
            self.killTimer(self._magnifier_timer)
            self._magnifier_timer = None
        self.magnifier.hide()
        self._pending_pos = None
        self._pending_item = None
        self._magnifier_active = False
        self._active_item = None
        self.magnifier_stopped.emit()
        super().leaveEvent(event)
