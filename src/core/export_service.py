from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict

from PIL import Image


@dataclass
class ExportConfig:
    max_prefix: str = "__"
    medium_prefix: str = "_"
    small_prefix: str = ""
    medium_width: int = 960
    small_width: int = 480
    format: str = "WEBP"
    quality: int = 85
    method: int = 4


class ExportServiceError(Exception):
    pass


class ExportService:
    def __init__(self, config: ExportConfig | None = None) -> None:
        self.config = config or ExportConfig()

    def export_variants(self, base_path: Path, variants: Dict[str, Image.Image]) -> list[Path]:
        if not variants:
            raise ExportServiceError("Keine Varianten verfügbar")

        output_paths: list[Path] = []
        stem = base_path.stem
        parent = base_path.parent

        mapping = {
            "max": f"{self.config.max_prefix}{stem}.webp",
            str(self.config.medium_width): f"{self.config.medium_prefix}{stem}.webp",
            str(self.config.small_width): f"{self.config.small_prefix}{stem}.webp",
        }

        for key, filename in mapping.items():
            if key not in variants:
                continue
            target_path = parent / filename
            variants[key].save(
                target_path,
                format=self.config.format,
                quality=self.config.quality,
                method=self.config.method,
            )
            output_paths.append(target_path)

        return output_paths
