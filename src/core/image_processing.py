from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from PIL import Image, ImageFilter


@dataclass
class ProcessingConfig:
    """Configuration values for scaling + sharpening."""

    sharpen_radius: float = 1.2
    sharpen_percent: int = 120
    sharpen_threshold: int = 3
    resample_method: int = Image.Resampling.LANCZOS


@dataclass
class ImageVariant:
    label: str
    width: int
    height: int
    image: Image.Image


class ProcessingError(Exception):
    pass


class ProcessingPipeline:
    def __init__(self, config: ProcessingConfig | None = None) -> None:
        self.config = config or ProcessingConfig()

    def resize_with_quality(
        self, image: Image.Image, target_width: int, target_height: int | None = None
    ) -> Image.Image:
        if target_width <= 0:
            raise ProcessingError("Zielbreite muss größer als 0 sein.")
        width, height = image.size
        if target_height is None:
            aspect = height / width if width else 1.0
            target_height = max(1, int(round(target_width * aspect)))
        if target_width == width and target_height == height:
            resized = image.copy()
        else:
            resized = image.resize((target_width, target_height), self.config.resample_method)

        sharpened = resized.filter(
            ImageFilter.UnsharpMask(
                radius=self.config.sharpen_radius,
                percent=self.config.sharpen_percent,
                threshold=self.config.sharpen_threshold,
            )
        )
        return sharpened

    def generate_variants(
        self, image: Image.Image, target_widths: Iterable[int]
    ) -> list[ImageVariant]:
        variants: list[ImageVariant] = []
        for width in target_widths:
            processed = self.resize_with_quality(image, width)
            variants.append(
                ImageVariant(
                    label=f"{width}px",
                    width=processed.width,
                    height=processed.height,
                    image=processed,
                )
            )
        return variants
