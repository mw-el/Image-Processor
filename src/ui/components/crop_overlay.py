from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import QRectF, Qt, QPointF, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPen, QImage, QAction
from PySide6.QtWidgets import QWidget, QLabel, QMenu
from PIL import Image
from .magnifier_widget import MagnifierWidget


@dataclass
class CropSelection:
    rect: QRectF
    aspect_ratio: float


class CropOverlay(QWidget):
    """
    Lightweight overlay that draws a ratio-constrained rectangle.
    Provides dragging/resizing while preserving the aspect ratio.
    """

    # Signal emitted when crop should be applied (double-click or context menu)
    crop_requested = Signal()

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

        # Magnifier setup (using reusable widget with 400px size)
        self.magnifier_label = MagnifierWidget(self, size=400)
        self._canvas_image: Optional[Image.Image] = None
        self._canvas_rect: QRectF = QRectF()
        self._canvas_scale: float = 1.0

    def set_selection(self, rect: QRectF, ratio: float) -> None:
        self._selection = CropSelection(rect=rect, aspect_ratio=ratio)
        self.show()  # Ensure overlay is visible
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

    def mouseDoubleClickEvent(self, event) -> None:
        """Handle double-click to apply crop."""
        if not self._selection:
            event.ignore()
            return
        if event.button() == Qt.LeftButton and self._selection.rect.contains(event.position()):
            self.crop_requested.emit()
            event.accept()
        else:
            event.ignore()

    def contextMenuEvent(self, event) -> None:
        """Show context menu with crop option."""
        if not self._selection:
            return
        if not self._selection.rect.contains(event.pos()):
            return

        menu = QMenu(self)
        apply_action = QAction("Ausschnitt übernehmen", self)
        apply_action.triggered.connect(self.crop_requested.emit)
        menu.addAction(apply_action)
        menu.exec(event.globalPos())

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
        """Update magnifier position and content using reusable widget."""
        self.magnifier_label.update_magnifier(
            cursor_pos,
            self._canvas_image,
            self._canvas_rect,
            self._canvas_scale,
            (self.width(), self.height())
        )
