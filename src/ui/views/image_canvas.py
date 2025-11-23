from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QRectF, QRect, Signal, QSize
from PySide6.QtGui import QPainter, QPixmap, QPalette, QImage
from PySide6.QtWidgets import QWidget, QSizePolicy, QLabel, QPushButton, QVBoxLayout

from ..components.crop_overlay import CropOverlay
from PIL import Image, ImageQt

try:
    import qtawesome as qta
    HAS_QTAWESOME = True
except ImportError:
    HAS_QTAWESOME = False


class ImageCanvas(QWidget):
    """
    Displays image pixmap and hosts crop overlay with fit-to-canvas + zoom behaviour.
    """

    # Signals for navigation
    navigate_previous = Signal()
    navigate_next = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setObjectName("imageCanvas")
        self._pixmap: Optional[QPixmap] = None
        self._pil_image: Optional[Image.Image] = None
        self._fit_scale: float = 1.0
        self._zoom_factor: float = 1.0
        self._image_rect: QRectF = QRectF()
        self.crop_overlay = CropOverlay(self)
        self.crop_overlay.setGeometry(self.rect())
        self.crop_overlay.raise_()

        # Navigation buttons
        self._create_nav_buttons()

    def _create_nav_buttons(self) -> None:
        """Create navigation buttons on left and right edges."""
        nav_btn_style = """
            QPushButton {
                background-color: rgba(33, 150, 243, 0.7);
                border: none;
                border-radius: 24px;
            }
            QPushButton:hover {
                background-color: rgba(25, 118, 210, 0.9);
            }
            QPushButton:pressed {
                background-color: rgba(13, 71, 161, 0.9);
            }
            QPushButton:disabled {
                background-color: rgba(158, 158, 158, 0.5);
            }
        """

        # Previous button (left)
        self.prev_btn = QPushButton(self)
        if HAS_QTAWESOME:
            self.prev_btn.setIcon(qta.icon("mdi6.chevron-left", color="white"))
        else:
            self.prev_btn.setText("<")
        self.prev_btn.setIconSize(QSize(32, 32))
        self.prev_btn.setFixedSize(48, 48)
        self.prev_btn.setStyleSheet(nav_btn_style)
        self.prev_btn.setCursor(Qt.PointingHandCursor)
        self.prev_btn.setToolTip("Vorheriges Bild")
        self.prev_btn.clicked.connect(self.navigate_previous.emit)
        self.prev_btn.hide()

        # Next button (right)
        self.next_btn = QPushButton(self)
        if HAS_QTAWESOME:
            self.next_btn.setIcon(qta.icon("mdi6.chevron-right", color="white"))
        else:
            self.next_btn.setText(">")
        self.next_btn.setIconSize(QSize(32, 32))
        self.next_btn.setFixedSize(48, 48)
        self.next_btn.setStyleSheet(nav_btn_style)
        self.next_btn.setCursor(Qt.PointingHandCursor)
        self.next_btn.setToolTip("Nächstes Bild")
        self.next_btn.clicked.connect(self.navigate_next.emit)
        self.next_btn.hide()

    def set_navigation_enabled(self, has_prev: bool, has_next: bool) -> None:
        """Enable/disable and show/hide navigation buttons."""
        self.prev_btn.setEnabled(has_prev)
        self.next_btn.setEnabled(has_next)
        # Show buttons if image is loaded
        if self._pixmap:
            self.prev_btn.show()
            self.next_btn.show()
            self._position_nav_buttons()
        else:
            self.prev_btn.hide()
            self.next_btn.hide()

    def _position_nav_buttons(self) -> None:
        """Position navigation buttons at left and right edges."""
        margin = 10
        center_y = self.height() // 2 - 24

        # Left button
        self.prev_btn.move(margin, center_y)

        # Right button
        self.next_btn.move(self.width() - 48 - margin, center_y)

    def load_image(self, path: Path) -> None:
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            raise ValueError("Bild konnte nicht geladen werden.")
        self._pixmap = pixmap
        self._zoom_factor = 1.0
        self._update_scaling()

    def clear(self) -> None:
        self._pixmap = None
        self._pil_image = None
        self._image_rect = QRectF()
        self.crop_overlay.clear_selection()
        self.update()

    def current_pixmap(self) -> Optional[QPixmap]:
        return self._pixmap

    def display_pil_image(self, image: Image.Image) -> None:
        image_qt = ImageQt.ImageQt(image)
        pixmap = QPixmap.fromImage(image_qt)
        self._pixmap = pixmap
        self._pil_image = image.copy()
        self._update_scaling()
        self._update_crop_overlay_info()

    def current_qimage(self):
        if not self._pixmap:
            return None
        return self._pixmap.toImage()

    def set_zoom_factor(self, factor: float) -> None:
        factor = max(0.1, min(2.0, factor))
        if abs(factor - self._zoom_factor) < 1e-4:
            return
        self._zoom_factor = factor
        self._update_scaling()

    def current_scale(self) -> float:
        return self._fit_scale * self._zoom_factor

    def image_rect_in_canvas(self) -> QRectF:
        return QRectF(self._image_rect)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        palette = self.palette()
        painter.fillRect(self.rect(), palette.color(QPalette.Base))
        if not self._pixmap:
            return
        target = self._image_rect
        if target.isNull():
            return
        source = QRectF(0, 0, self._pixmap.width(), self._pixmap.height())
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        painter.drawPixmap(target, self._pixmap, source)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_scaling()
        self._position_nav_buttons()

    def _resize_overlay(self) -> None:
        if not self._pixmap:
            self.crop_overlay.hide()
            return
        self.crop_overlay.setGeometry(self.rect())
        self.crop_overlay.show()

    def _update_scaling(self) -> None:
        if not self._pixmap:
            self._fit_scale = 1.0
            self._image_rect = QRectF()
            self._resize_overlay()
            self.update()
            return

        pixmap_w = self._pixmap.width()
        pixmap_h = self._pixmap.height()
        if pixmap_w <= 0 or pixmap_h <= 0:
            self._image_rect = QRectF()
            self.update()
            return

        avail_w = max(1, self.width())
        avail_h = max(1, self.height())
        self._fit_scale = min(avail_w / pixmap_w, avail_h / pixmap_h)
        scale = self.current_scale()
        scaled_w = pixmap_w * scale
        scaled_h = pixmap_h * scale
        offset_x = (avail_w - scaled_w) / 2
        offset_y = (avail_h - scaled_h) / 2
        self._image_rect = QRectF(offset_x, offset_y, scaled_w, scaled_h)
        self._resize_overlay()
        self._update_crop_overlay_info()
        self.update()

    def _update_crop_overlay_info(self) -> None:
        """Update crop overlay with canvas information for magnifier."""
        if hasattr(self, 'crop_overlay'):
            self.crop_overlay.set_canvas_info(
                self._pil_image,
                self._image_rect,
                self.current_scale()
            )
