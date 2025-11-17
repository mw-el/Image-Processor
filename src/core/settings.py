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
class VariantRule:
    prefix: str
    width: str | int
    height: str | int


@dataclass
class ExportSettings:
    format: str
    quality: int
    method: int
    variant_rules: dict[str, list[VariantRule]]


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
        "format": "WEBP",
        "quality": 85,
        "method": 4,
        "variant_rules": {
            "default": [
                {"prefix": "__", "width": "original", "height": "original"},
                {"prefix": "_", "width": 960, "height": "auto"},
                {"prefix": "", "width": 480, "height": "auto"},
            ],
            "16:9": [
                {"prefix": "__", "width": 3840, "height": 2160},
                {"prefix": "_", "width": 1920, "height": 1080},
                {"prefix": "", "width": 1280, "height": 720},
            ],
            "9:16": [
                {"prefix": "__", "width": 2160, "height": 3840},
                {"prefix": "_", "width": 1080, "height": 1920},
                {"prefix": "", "width": 720, "height": 1280},
            ],
        },
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

    variant_rules_cfg = export.get("variant_rules", DEFAULT_SETTINGS["export"].get("variant_rules", {}))
    variant_rules: dict[str, list[VariantRule]] = {}
    for label, rules in variant_rules_cfg.items():
        parsed_rules: list[VariantRule] = []
        for rule in rules:
            parsed_rules.append(
                VariantRule(
                    prefix=str(rule.get("prefix", "")),
                    width=rule.get("width", "original"),
                    height=rule.get("height", "auto"),
                )
            )
        variant_rules[label] = parsed_rules

    export_settings = ExportSettings(
        format=str(export.get("format", "WEBP")),
        quality=int(export.get("quality", 85)),
        method=int(export.get("method", 4)),
        variant_rules=variant_rules,
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
