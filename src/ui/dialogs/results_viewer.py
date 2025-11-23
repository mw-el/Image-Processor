from __future__ import annotations

from pathlib import Path
from typing import Optional

from PIL import Image
from PySide6.QtCore import Qt, QPoint, QRect, QSize
from PySide6.QtGui import QPixmap, QPainter, QImage
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QGridLayout,
    QLabel,
    QScrollArea,
    QWidget,
    QPushButton,
    QHBoxLayout,
)


def pil_to_qpixmap(pil_image: Image.Image) -> QPixmap:
    """Convert PIL Image to QPixmap."""
    img_rgb = pil_image.convert("RGB")
    data = img_rgb.tobytes("raw", "RGB")
    qimage = QImage(data, img_rgb.width, img_rgb.height, img_rgb.width * 3, QImage.Format_RGB888)
    return QPixmap.fromImage(qimage)


class ImageThumbnail(QLabel):
    """Thumbnail widget that shows an image and info text."""

    def __init__(self, image_path: Path, is_original: bool = False, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.image_path = image_path
        self.is_original = is_original
        self.pil_image: Optional[Image.Image] = None
        self.thumbnail_size = 300

        # Load image
        try:
            self.pil_image = Image.open(image_path)
        except Exception as e:
            self.setText(f"Fehler: {e}")
            return

        # Create thumbnail
        thumb = self.pil_image.copy()
        thumb.thumbnail((self.thumbnail_size, self.thumbnail_size), Image.Resampling.LANCZOS)
        pixmap = pil_to_qpixmap(thumb)
        self.setPixmap(pixmap)

        # Set properties
        self.setAlignment(Qt.AlignCenter)
        self.setFrameStyle(QLabel.Box | QLabel.Plain)
        self.setLineWidth(1)
        self.setMinimumSize(self.thumbnail_size + 20, self.thumbnail_size + 40)

        # Info text
        label_text = "ORIGINAL" if is_original else image_path.name
        resolution = f"{self.pil_image.width}×{self.pil_image.height}"
        self.setToolTip(f"{label_text}\n{resolution}")

        # For displaying info below thumbnail
        self.info_label = QLabel(f"<b>{label_text}</b><br>{resolution}")
        self.info_label.setAlignment(Qt.AlignCenter)
        self.info_label.setWordWrap(True)


class ResultsViewerDialog(QDialog):
    """Dialog showing original and exported images in a grid with hover magnifier."""

    def __init__(
        self, original_path: Path, exported_paths: list[Path], parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Ergebnisse anschauen")
        self.resize(1200, 800)

        self.original_path = original_path
        self.exported_paths = exported_paths
        self.thumbnails: list[ImageThumbnail] = []

        # Magnifier state
        self.magnifier_active = False
        self.current_hover_thumbnail: Optional[ImageThumbnail] = None
        self.magnifier_label: Optional[QLabel] = None

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Title
        title = QLabel("<h2>Exportierte Ergebnisse</h2>")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Scroll area for grid
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # Container for grid
        grid_container = QWidget()
        grid_layout = QGridLayout(grid_container)
        grid_layout.setSpacing(20)

        # Add original image
        original_thumb = ImageThumbnail(self.original_path, is_original=True)
        original_thumb.setMouseTracking(True)
        original_thumb.enterEvent = lambda event: self._on_thumbnail_enter(original_thumb)
        original_thumb.leaveEvent = lambda event: self._on_thumbnail_leave()
        original_thumb.mouseMoveEvent = lambda event: self._on_mouse_move(event, original_thumb)

        thumb_container = QVBoxLayout()
        thumb_container.addWidget(original_thumb)
        thumb_container.addWidget(original_thumb.info_label)

        container_widget = QWidget()
        container_widget.setLayout(thumb_container)
        grid_layout.addWidget(container_widget, 0, 0)
        self.thumbnails.append(original_thumb)

        # Add exported images
        for idx, path in enumerate(self.exported_paths, start=1):
            export_thumb = ImageThumbnail(path, is_original=False)
            export_thumb.setMouseTracking(True)
            export_thumb.enterEvent = lambda event, t=export_thumb: self._on_thumbnail_enter(t)
            export_thumb.leaveEvent = lambda event: self._on_thumbnail_leave()
            export_thumb.mouseMoveEvent = lambda event, t=export_thumb: self._on_mouse_move(event, t)

            thumb_container = QVBoxLayout()
            thumb_container.addWidget(export_thumb)
            thumb_container.addWidget(export_thumb.info_label)

            container_widget = QWidget()
            container_widget.setLayout(thumb_container)

            row = idx // 3
            col = idx % 3
            grid_layout.addWidget(container_widget, row, col)
            self.thumbnails.append(export_thumb)

        scroll.setWidget(grid_container)
        layout.addWidget(scroll)

        # Magnifier overlay (initially hidden)
        self.magnifier_label = QLabel(self)
        self.magnifier_label.setFrameStyle(QLabel.Box | QLabel.Plain)
        self.magnifier_label.setLineWidth(2)
        self.magnifier_label.hide()
        self.magnifier_label.setStyleSheet("border: 2px solid #ff6600; background: white;")

        # Close button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        close_btn = QPushButton("Schließen")
        close_btn.clicked.connect(self.accept)
        close_btn.setFixedWidth(120)
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)

    def _on_thumbnail_enter(self, thumbnail: ImageThumbnail) -> None:
        """Mouse enters thumbnail - prepare magnifier."""
        self.current_hover_thumbnail = thumbnail
        self.magnifier_active = True

    def _on_thumbnail_leave(self) -> None:
        """Mouse leaves thumbnail - hide magnifier."""
        self.magnifier_active = False
        self.current_hover_thumbnail = None
        if self.magnifier_label:
            self.magnifier_label.hide()

    def _on_mouse_move(self, event, thumbnail: ImageThumbnail) -> None:
        """Mouse moves over thumbnail - update magnifier."""
        if not self.magnifier_active or not thumbnail.pil_image or not self.magnifier_label:
            return

        # Get mouse position relative to thumbnail
        local_pos = event.pos()

        # Calculate which part of the original image to show
        thumb_rect = thumbnail.pixmap().rect() if thumbnail.pixmap() else QRect()
        if thumb_rect.isEmpty():
            return

        # Map position to original image coordinates
        scale_x = thumbnail.pil_image.width / thumb_rect.width()
        scale_y = thumbnail.pil_image.height / thumb_rect.height()

        center_x = int(local_pos.x() * scale_x)
        center_y = int(local_pos.y() * scale_y)

        # Define magnifier size (e.g., 400x400 pixels)
        mag_size = 400
        crop_size = mag_size  # Show 1:1 scale (100%)

        # Calculate crop region
        left = max(0, center_x - crop_size // 2)
        top = max(0, center_y - crop_size // 2)
        right = min(thumbnail.pil_image.width, left + crop_size)
        bottom = min(thumbnail.pil_image.height, top + crop_size)

        # Adjust if we hit image boundaries
        if right - left < crop_size:
            left = max(0, right - crop_size)
        if bottom - top < crop_size:
            top = max(0, bottom - crop_size)

        # Crop and display
        try:
            cropped = thumbnail.pil_image.crop((left, top, right, bottom))
            pixmap = pil_to_qpixmap(cropped)
            self.magnifier_label.setPixmap(pixmap)
            self.magnifier_label.resize(pixmap.size())

            # Position magnifier near cursor
            global_pos = event.globalPos()
            dialog_pos = self.mapFromGlobal(global_pos)

            # Offset magnifier to the right and below cursor
            offset_x = 20
            offset_y = 20

            mag_x = dialog_pos.x() + offset_x
            mag_y = dialog_pos.y() + offset_y

            # Keep magnifier within dialog bounds
            if mag_x + self.magnifier_label.width() > self.width():
                mag_x = dialog_pos.x() - self.magnifier_label.width() - offset_x

            if mag_y + self.magnifier_label.height() > self.height():
                mag_y = dialog_pos.y() - self.magnifier_label.height() - offset_y

            self.magnifier_label.move(mag_x, mag_y)
            self.magnifier_label.show()
            self.magnifier_label.raise_()

        except Exception:
            pass  # Silently ignore crop errors
