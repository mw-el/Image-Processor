from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QSizePolicy

from ..components.crop_overlay import CropOverlay
from PIL import Image, ImageQt


class ImageCanvas(QLabel):
    """
    Displays image pixmap and hosts crop overlay.
    Currently uses QLabel; will be replaced with custom widget when we add full interactivity.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setObjectName("imageCanvas")
        self.setScaledContents(True)
        self._pixmap: Optional[QPixmap] = None
        self.crop_overlay = CropOverlay(self)

    def load_image(self, path: Path) -> None:
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            raise ValueError("Bild konnte nicht geladen werden.")
        self._pixmap = pixmap
        self.setPixmap(pixmap)
        self._resize_overlay()

    def clear(self) -> None:
        self._pixmap = None
        self.setPixmap(QPixmap())
        self.crop_overlay.clear_selection()

    def current_pixmap(self) -> Optional[QPixmap]:
        return self._pixmap

    def display_pil_image(self, image: Image.Image) -> None:
        image_qt = ImageQt.ImageQt(image)
        pixmap = QPixmap.fromImage(image_qt)
        self._pixmap = pixmap
        self.setPixmap(pixmap)
        self._resize_overlay()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._resize_overlay()

    def _resize_overlay(self) -> None:
        if not self._pixmap:
            self.crop_overlay.hide()
            return
        self.crop_overlay.setGeometry(self.rect())
        self.crop_overlay.show()
