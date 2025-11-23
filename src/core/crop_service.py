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


def compute_crop_box(
    selection_rect: QRectF,
    image_rect: QRectF,
    pixmap: QPixmap,
    current_scale: float,
) -> CropResult:
    if image_rect.width() <= 0 or image_rect.height() <= 0:
        raise CropServiceError("Ungültige Bildprojektion.")
    if pixmap.isNull():
        raise CropServiceError("Kein Bild geladen.")
    if current_scale <= 0:
        raise CropServiceError("Ungültiger Zoomfaktor.")

    intersection = selection_rect.intersected(image_rect)
    if not intersection.isValid() or intersection.width() <= 0 or intersection.height() <= 0:
        raise CropServiceError("Auswahl enthält keinen sichtbaren Bildanteil.")

    left = max(0, int(round((intersection.x() - image_rect.x()) / current_scale)))
    top = max(0, int(round((intersection.y() - image_rect.y()) / current_scale)))
    width = max(1, int(round(intersection.width() / current_scale)))
    height = max(1, int(round(intersection.height() / current_scale)))

    image_width = pixmap.width()
    image_height = pixmap.height()
    if left + width > image_width:
        width = max(1, image_width - left)
    if top + height > image_height:
        height = max(1, image_height - top)

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
