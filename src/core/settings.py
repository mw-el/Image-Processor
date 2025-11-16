from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image


@dataclass
class ProcessingSettings:
    variant_widths: list[int]
    sharpen_radius: float
    sharpen_percent: int
    sharpen_threshold: int
    resample_method: int


@dataclass
class ExportSettings:
    max_prefix: str
    medium_prefix: str
    small_prefix: str
    medium_width: int
    small_width: int
    format: str
    quality: int
    method: int


@dataclass
class AppSettings:
    processing: ProcessingSettings
    export: ExportSettings


DEFAULT_SETTINGS = {
    "processing": {
        "variant_widths": [960, 480],
        "sharpen_radius": 1.2,
        "sharpen_percent": 120,
        "sharpen_threshold": 3,
        "resample_method": "LANCZOS",
    },
    "export": {
        "max_prefix": "__",
        "medium_prefix": "_",
        "small_prefix": "",
        "medium_width": 960,
        "small_width": 480,
        "format": "WEBP",
        "quality": 85,
        "method": 4,
    },
}


def load_settings(path: Path | None = None) -> AppSettings:
    base_path = path or Path(__file__).resolve().parents[1] / "config" / "settings.json"
    data = DEFAULT_SETTINGS
    if base_path.exists():
        try:
            with base_path.open("r", encoding="utf-8") as fh:
                file_data = json.load(fh)
                data = _merge_settings(DEFAULT_SETTINGS, file_data)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Settings-Datei ungültig: {exc}") from exc

    processing = data["processing"]
    export = data["export"]

    resample_attr = processing.get("resample_method", "LANCZOS")
    resample_method = getattr(Image.Resampling, resample_attr, Image.Resampling.LANCZOS)

    processing_settings = ProcessingSettings(
        variant_widths=list(processing.get("variant_widths", [960, 480])),
        sharpen_radius=float(processing.get("sharpen_radius", 1.2)),
        sharpen_percent=int(processing.get("sharpen_percent", 120)),
        sharpen_threshold=int(processing.get("sharpen_threshold", 3)),
        resample_method=resample_method,
    )

    export_settings = ExportSettings(
        max_prefix=str(export.get("max_prefix", "__")),
        medium_prefix=str(export.get("medium_prefix", "_")),
        small_prefix=str(export.get("small_prefix", "")),
        medium_width=int(export.get("medium_width", 960)),
        small_width=int(export.get("small_width", 480)),
        format=str(export.get("format", "WEBP")),
        quality=int(export.get("quality", 85)),
        method=int(export.get("method", 4)),
    )

    return AppSettings(processing=processing_settings, export=export_settings)


def _merge_settings(default: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for key, value in default.items():
        if key in overrides:
            if isinstance(value, dict) and isinstance(overrides[key], dict):
                merged[key] = _merge_settings(value, overrides[key])
            else:
                merged[key] = overrides[key]
        else:
            merged[key] = value
    # Include extra keys from overrides
    for key, value in overrides.items():
        if key not in merged:
            merged[key] = value
    return merged
