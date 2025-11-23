from __future__ import annotations

from PIL import Image


def resize_for_variant(
    image: Image.Image,
    target_width: int,
    target_height: int,
    *,
    resample_filter: int = Image.Resampling.LANCZOS,
) -> Image.Image:
    """
    Resize image to target dimensions using LANCZOS resampling.

    Args:
        image: Source image
        target_width: Target width in pixels
        target_height: Target height in pixels
        resample_filter: PIL resampling filter (default: LANCZOS)

    Returns:
        Resized image
    """
    if target_width <= 0 or target_height <= 0:
        raise ValueError("Zieldimensionen müssen größer als 0 sein.")

    src_width, src_height = image.size
    if src_width <= 0 or src_height <= 0:
        raise ValueError("Ungültige Bildquelle.")

    return image.resize((target_width, target_height), resample_filter)


__all__ = ["resize_for_variant"]
