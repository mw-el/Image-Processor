from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Optional

from PIL import Image

from .adjustments import AdjustmentState, apply_adjustments
from .settings import AppSettings, VariantRule


class ImageSessionError(RuntimeError):
    pass


@dataclass
class RatioSelection:
    label: Optional[str] = None
    value: Optional[float] = None
    custom_tuple: Optional[tuple[float, float]] = None


class ImageSession:
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        self.path: Optional[Path] = None
        self.original_image: Optional[Image.Image] = None
        self.base_image: Optional[Image.Image] = None
        self.ratio = RatioSelection()

    def load(self, path: Path) -> Image.Image:
        try:
            pil = Image.open(path).convert("RGB")
        except Exception as exc:  # pragma: no cover
            raise ImageSessionError(f"Bild konnte nicht geladen werden: {exc}") from exc
        self.path = path
        self.original_image = pil
        self.base_image = pil.copy()
        self.ratio = RatioSelection()
        return self.base_image.copy()

    def has_image(self) -> bool:
        return self.base_image is not None

    def current_base(self) -> Image.Image:
        if self.base_image is None:
            raise ImageSessionError("Kein Bild geladen.")
        return self.base_image.copy()

    def set_base_image(self, image: Image.Image) -> None:
        self.base_image = image.copy()

    def reset_base_to_original(self) -> Image.Image:
        if self.original_image is None:
            raise ImageSessionError("Kein Bild geladen.")
        self.base_image = self.original_image.copy()
        return self.base_image.copy()

    def set_ratio(self, label: Optional[str], value: Optional[float], custom: Optional[tuple[float, float]]) -> None:
        self.ratio = RatioSelection(label, value, custom)

    def clear_ratio(self) -> None:
        self.ratio = RatioSelection()

    def apply_adjustments(self, state: AdjustmentState) -> Image.Image:
        base = self.current_base()
        return apply_adjustments(base, state)

    def build_variant_specs(self, image: Image.Image) -> tuple[list[tuple[str, int, int]], str]:
        label = self.ratio.label
        value = self.ratio.value
        if value is None or value <= 0:
            label, value = self._derive_ratio(image)
        if not label:
            label = "default"
        rules = self._variant_rules(label)
        specs: list[tuple[str, int, int]] = []
        for rule in rules:
            width, height = self._resolve_dimensions(rule, image, value)
            specs.append((rule.prefix, width, height))
        suffix = label.replace(":", "x").replace(" ", "").replace("?", "custom")
        return specs, suffix

    def _variant_rules(self, label: str) -> list[VariantRule]:
        rules = self.settings.export.variant_rules.get(label)
        if not rules:
            rules = self.settings.export.variant_rules.get("default", [])
        if not rules:
            raise ImageSessionError("Keine Exportregeln konfiguriert.")
        return rules

    def _derive_ratio(self, image: Image.Image) -> tuple[str, float]:
        width, height = image.size
        if height == 0:
            return "default", 1.0
        frac = Fraction(width, height).limit_denominator(100)
        return f"{frac.numerator}:{frac.denominator}", width / height

    def _resolve_dimensions(
        self, rule: VariantRule, image: Image.Image, ratio_value: float
    ) -> tuple[int, int]:
        def resolve(value, original, *, is_width: bool, other: Optional[int] = None) -> int:
            if isinstance(value, str):
                lowered = value.lower()
                if lowered == "original":
                    return original
                if lowered == "auto":
                    if other is None or ratio_value == 0:
                        return original
                    if is_width:
                        return max(1, int(round(other * ratio_value)))
                    return max(1, int(round(other / ratio_value)))
            return int(value)

        width_auto = isinstance(rule.width, str) and rule.width.lower() == "auto"
        height_auto = isinstance(rule.height, str) and rule.height.lower() == "auto"

        width = resolve(rule.width, image.width, is_width=True)
        height = resolve(rule.height, image.height, is_width=False, other=width)

        if width_auto and not height_auto:
            width = max(1, int(round(height * ratio_value)))
        if height_auto and not width_auto:
            height = max(1, int(round(width / ratio_value)))
        if width_auto and height_auto:
            return image.width, image.height

        return width, height
