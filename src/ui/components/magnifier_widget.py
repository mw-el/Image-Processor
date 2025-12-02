from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel
from PIL import Image


class MagnifierWidget(QLabel):
    """
    Reusable magnifier widget that shows 1:1 pixel view of image area under cursor.

    KISS: Simple QLabel with pixmap, no complex logic.
    """

    def __init__(self, parent=None, size: int = 150) -> None:
        super().__init__(parent)
        self.setFrameStyle(QLabel.Box | QLabel.Plain)
        self.setLineWidth(2)
        self.setStyleSheet("border: 2px solid #ff6600; background: white;")
        self.hide()
        self._magnifier_size = size

    def update_magnifier(
        self,
        cursor_pos: QPointF,
        image: Image.Image,
        image_rect: QRectF,
        scale: float,
        parent_size: tuple[int, int]
    ) -> None:
        """
        Update magnifier position and content.

        Args:
            cursor_pos: Current cursor position in parent coordinates
            image: PIL Image to magnify
            image_rect: Rectangle where image is displayed in parent
            scale: Current display scale of image
            parent_size: (width, height) of parent widget for boundary checking
        """
        if not image or not image_rect.isValid() or scale <= 0:
            self.hide()
            return

        # Map cursor position to image coordinates
        local_x = cursor_pos.x() - image_rect.x()
        local_y = cursor_pos.y() - image_rect.y()

        # Check if cursor is within image bounds
        if local_x < 0 or local_y < 0 or local_x > image_rect.width() or local_y > image_rect.height():
            self.hide()
            return

        # Convert to original image coordinates
        img_x = int(local_x / scale)
        img_y = int(local_y / scale)

        # Calculate crop region in original image (1:1 scale)
        crop_size = self._magnifier_size
        left = max(0, img_x - crop_size // 2)
        top = max(0, img_y - crop_size // 2)
        right = min(image.width, left + crop_size)
        bottom = min(image.height, top + crop_size)

        # Adjust if we hit image boundaries
        if right - left < crop_size:
            left = max(0, right - crop_size)
        if bottom - top < crop_size:
            top = max(0, bottom - crop_size)

        # Crop and display
        try:
            cropped = image.crop((left, top, right, bottom))

            # Convert PIL to QPixmap
            img_rgb = cropped.convert("RGB")
            data = img_rgb.tobytes("raw", "RGB")
            qimage = QImage(data, img_rgb.width, img_rgb.height, img_rgb.width * 3, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(qimage)

            self.setPixmap(pixmap)
            self.resize(pixmap.size())

            # Position magnifier near cursor (right-bottom by default)
            offset = 20
            mag_x = int(cursor_pos.x() + offset)
            mag_y = int(cursor_pos.y() + offset)

            parent_width, parent_height = parent_size

            # If magnifier would go off screen right, move to left
            if mag_x + self.width() > parent_width:
                mag_x = int(cursor_pos.x() - self.width() - offset)

            # If magnifier would go off screen bottom, move to top
            if mag_y + self.height() > parent_height:
                mag_y = int(cursor_pos.y() - self.height() - offset)

            self.move(mag_x, mag_y)
            self.show()
            self.raise_()

        except Exception:
            # Fail Fast: Hide on any error
            self.hide()
