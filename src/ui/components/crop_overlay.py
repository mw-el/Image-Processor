from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import QRectF, Qt, QPointF
from PySide6.QtGui import QBrush, QColor, QPainter, QPen, QImage
from PySide6.QtWidgets import QWidget, QLabel
from PIL import Image


@dataclass
class CropSelection:
    rect: QRectF
    aspect_ratio: float


class CropOverlay(QWidget):
    """
    Lightweight overlay that draws a ratio-constrained rectangle.
    Provides dragging/resizing while preserving the aspect ratio.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.setMouseTracking(True)
        self._selection: Optional[CropSelection] = None
        self._overlay_color = QColor(255, 0, 0, 50)
        self._border_color = QColor(255, 0, 0)
        self._dragging = False
        self._resizing = False
        self._drag_offset = QPointF()
        self._active_handle: Optional[str] = None
        self.handle_size = 12

        # Magnifier setup
        self.magnifier_label = QLabel(self)
        self.magnifier_label.setFrameStyle(QLabel.Box | QLabel.Plain)
        self.magnifier_label.setLineWidth(2)
        self.magnifier_label.hide()
        self.magnifier_label.setStyleSheet("border: 2px solid #ff6600; background: white;")
        self._canvas_image: Optional[Image.Image] = None
        self._canvas_rect: QRectF = QRectF()
        self._canvas_scale: float = 1.0

    def set_selection(self, rect: QRectF, ratio: float) -> None:
        self._selection = CropSelection(rect=rect, aspect_ratio=ratio)
        self.update()

    def clear_selection(self) -> None:
        self._selection = None
        self.magnifier_label.hide()
        self.update()

    def current_selection(self) -> Optional[CropSelection]:
        return self._selection

    def set_canvas_info(self, pil_image: Optional[Image.Image], image_rect: QRectF, scale: float) -> None:
        """Set canvas information for magnifier functionality."""
        self._canvas_image = pil_image.copy() if pil_image else None
        self._canvas_rect = QRectF(image_rect)
        self._canvas_scale = scale

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if not self._selection:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        pen = QPen(self._border_color, 2)
        painter.setPen(pen)
        painter.setBrush(QBrush(self._overlay_color))
        painter.drawRect(self._selection.rect)
        self._draw_handles(painter)

    # Interaction handling ----------------------------------------------------
    def mousePressEvent(self, event) -> None:
        if not self._selection:
            event.ignore()
            return
        if event.button() != Qt.LeftButton:
            event.ignore()
            return

        handle = self._hit_test_handles(event.position())
        if handle:
            self._resizing = True
            self._active_handle = handle
        elif self._selection.rect.contains(event.position()):
            self._dragging = True
            self._drag_offset = event.position() - self._selection.rect.topLeft()
        else:
            event.ignore()
            return
        event.accept()

    def mouseMoveEvent(self, event) -> None:
        # Handle crop operations if active
        if self._dragging or self._resizing:
            if self._dragging:
                new_top_left = event.position() - self._drag_offset
                self._move_selection(new_top_left)
            elif self._resizing:
                self._resize_selection(event.position())
            self.update()
            event.accept()
            self.magnifier_label.hide()
            return

        # Show magnifier if mouse is over image and not near handles
        if self._canvas_image and self._canvas_rect.contains(event.position()):
            # Check if near handles
            near_handle = False
            if self._selection:
                near_handle = self._hit_test_handles(event.position()) is not None

            if not near_handle:
                self._update_magnifier(event.position())
            else:
                self.magnifier_label.hide()
        else:
            self.magnifier_label.hide()

        event.ignore()  # Let parent handle if not consumed

    def mouseReleaseEvent(self, event) -> None:
        if event.button() != Qt.LeftButton:
            event.ignore()
            return
        self._dragging = False
        self._resizing = False
        self._active_handle = None
        event.accept()

    # Internal helpers -------------------------------------------------------
    def _draw_handles(self, painter: QPainter) -> None:
        if not self._selection:
            return
        handle_positions = self._calculate_handle_positions()
        painter.setBrush(QBrush(QColor(255, 255, 255)))
        painter.setPen(QPen(self._border_color, 1))
        for pos in handle_positions.values():
            rect = QRectF(pos.x() - self.handle_size / 2, pos.y() - self.handle_size / 2, self.handle_size, self.handle_size)
            painter.drawRect(rect)

    def _calculate_handle_positions(self) -> dict[str, QPointF]:
        rect = self._selection.rect
        return {
            "top_left": rect.topLeft(),
            "top_right": rect.topRight(),
            "bottom_left": rect.bottomLeft(),
            "bottom_right": rect.bottomRight(),
        }

    def _hit_test_handles(self, point: QPointF) -> Optional[str]:
        handles = self._calculate_handle_positions()
        for name, pos in handles.items():
            rect = QRectF(pos.x() - self.handle_size, pos.y() - self.handle_size, self.handle_size * 2, self.handle_size * 2)
            if rect.contains(point):
                return name
        return None

    def _move_selection(self, new_top_left: QPointF) -> None:
        rect = QRectF(new_top_left, self._selection.rect.size())
        rect = self._confine_to_bounds(rect)
        self._selection = CropSelection(rect=rect, aspect_ratio=self._selection.aspect_ratio)

    def _resize_selection(self, cursor_pos: QPointF) -> None:
        # Simplified resize keeping aspect ratio; adjust width based on horizontal distance.
        bounds = self.rect()
        rect = self._selection.rect
        center = rect.center()
        width = abs(cursor_pos.x() - center.x()) * 2
        height = width / self._selection.aspect_ratio
        if height > bounds.height():
            height = bounds.height()
            width = height * self._selection.aspect_ratio
        new_rect = QRectF(center.x() - width / 2, center.y() - height / 2, width, height)
        new_rect = self._confine_to_bounds(new_rect)
        self._selection = CropSelection(rect=new_rect, aspect_ratio=self._selection.aspect_ratio)

    def _confine_to_bounds(self, rect: QRectF) -> QRectF:
        bounds = self.rect()
        if rect.left() < bounds.left():
            rect.moveLeft(bounds.left())
        if rect.right() > bounds.right():
            rect.moveRight(bounds.right())
        if rect.top() < bounds.top():
            rect.moveTop(bounds.top())
        if rect.bottom() > bounds.bottom():
            rect.moveBottom(bounds.bottom())
        return rect

    def leaveEvent(self, event) -> None:
        """Hide magnifier when mouse leaves overlay."""
        self.magnifier_label.hide()
        super().leaveEvent(event)

    def _update_magnifier(self, cursor_pos) -> None:
        """Update magnifier position and content."""
        if not self._canvas_image or not self._canvas_rect.isValid():
            return

        # Map cursor position to image coordinates
        local_x = cursor_pos.x() - self._canvas_rect.x()
        local_y = cursor_pos.y() - self._canvas_rect.y()

        if self._canvas_scale <= 0:
            return

        # Convert to original image coordinates
        img_x = int(local_x / self._canvas_scale)
        img_y = int(local_y / self._canvas_scale)

        # Define magnifier size (400x400 pixels showing 1:1 scale)
        mag_size = 400
        crop_size = mag_size

        # Calculate crop region in original image
        left = max(0, img_x - crop_size // 2)
        top = max(0, img_y - crop_size // 2)
        right = min(self._canvas_image.width, left + crop_size)
        bottom = min(self._canvas_image.height, top + crop_size)

        # Adjust if we hit image boundaries
        if right - left < crop_size:
            left = max(0, right - crop_size)
        if bottom - top < crop_size:
            top = max(0, bottom - crop_size)

        # Crop and display
        try:
            cropped = self._canvas_image.crop((left, top, right, bottom))

            # Convert PIL to QPixmap
            img_rgb = cropped.convert("RGB")
            data = img_rgb.tobytes("raw", "RGB")
            from PySide6.QtGui import QPixmap
            qimage = QImage(data, img_rgb.width, img_rgb.height, img_rgb.width * 3, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(qimage)

            self.magnifier_label.setPixmap(pixmap)
            self.magnifier_label.resize(pixmap.size())

            # Position magnifier near cursor
            offset_x = 20
            offset_y = 20

            mag_x = int(cursor_pos.x() + offset_x)
            mag_y = int(cursor_pos.y() + offset_y)

            # Keep magnifier within overlay bounds
            if mag_x + self.magnifier_label.width() > self.width():
                mag_x = int(cursor_pos.x() - self.magnifier_label.width() - offset_x)

            if mag_y + self.magnifier_label.height() > self.height():
                mag_y = int(cursor_pos.y() - self.magnifier_label.height() - offset_y)

            self.magnifier_label.move(mag_x, mag_y)
            self.magnifier_label.show()
            self.magnifier_label.raise_()

        except Exception:
            pass  # Silently ignore crop errors
