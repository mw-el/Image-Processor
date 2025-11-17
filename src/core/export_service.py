from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from PIL import Image


@dataclass
class ExportVariant:
    prefix: str
    resolution: tuple[int, int]
    ratio_suffix: str
    image: Image.Image


@dataclass
class ExportConfig:
    format: str = "WEBP"
    quality: int = 85
    method: int = 4


class ExportServiceError(Exception):
    pass


class ExportService:
    def __init__(self, config: ExportConfig | None = None) -> None:
        self.config = config or ExportConfig()

    def export_variants(
        self,
        base_path: Path,
        variants: Iterable[ExportVariant],
        metadata_bytes: bytes | None = None,
    ) -> list[Path]:
        variants = list(variants)
        if not variants:
            raise ExportServiceError("Keine Varianten verfügbar")

        output_paths: list[Path] = []
        stem = base_path.stem
        parent = base_path.parent

        for variant in variants:
            width, height = variant.resolution
            ratio_suffix = variant.ratio_suffix
            filename = f"{variant.prefix}{stem}_{width}x{height}_{ratio_suffix}.webp"
            target_path = parent / filename
            save_kwargs = dict(
                format=self.config.format,
                quality=self.config.quality,
                method=self.config.method,
            )
            if metadata_bytes:
                save_kwargs["xmp"] = metadata_bytes
            variant.image.save(target_path, **save_kwargs)
            output_paths.append(target_path)

        return output_paths
