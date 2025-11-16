from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QRectF
from PySide6.QtGui import QPixmap
from PIL import Image, ImageQt


@dataclass
class CropResult:
    box: tuple[int, int, int, int]


class CropServiceError(Exception):
    pass


def compute_crop_box(selection_rect: QRectF, canvas_rect: QRectF, pixmap: QPixmap) -> CropResult:
    if canvas_rect.width() <= 0 or canvas_rect.height() <= 0:
        raise CropServiceError("Ungültige Canvas-Größe.")
    if pixmap.isNull():
        raise CropServiceError("Kein Bild geladen.")

    image_width = pixmap.width()
    image_height = pixmap.height()

    rel_x = (selection_rect.x() - canvas_rect.x()) / canvas_rect.width()
    rel_y = (selection_rect.y() - canvas_rect.y()) / canvas_rect.height()
    rel_w = selection_rect.width() / canvas_rect.width()
    rel_h = selection_rect.height() / canvas_rect.height()

    left = max(0, min(image_width, int(round(rel_x * image_width))))
    top = max(0, min(image_height, int(round(rel_y * image_height))))
    width = max(1, min(image_width - left, int(round(rel_w * image_width))))
    height = max(1, min(image_height - top, int(round(rel_h * image_height))))

    return CropResult(box=(left, top, width, height))


def perform_crop(pixmap: QPixmap, crop: CropResult) -> Image.Image:
    if pixmap.isNull():
        raise CropServiceError("Kein Bild geladen.")
    qimage = pixmap.toImage()
    pil_image = ImageQt.fromqimage(qimage)  # type: ignore[arg-type]
    left, top, width, height = crop.box
    right = left + width
    bottom = top + height
    return pil_image.crop((left, top, right, bottom))
