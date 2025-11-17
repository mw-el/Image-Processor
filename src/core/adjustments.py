from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageEnhance, ImageOps


@dataclass
class AdjustmentState:
    brightness: float = 1.0
    contrast: float = 1.0
    saturation: float = 1.0
    sharpness: float = 1.0
    temperature: int = 0  # -100 .. 100


def _clamp_factor(value: float, minimum: float = 0.2, maximum: float = 3.0) -> float:
    return float(max(minimum, min(maximum, value)))


def set_brightness(state: AdjustmentState, value: float) -> None:
    state.brightness = _clamp_factor(value)


def set_contrast(state: AdjustmentState, value: float) -> None:
    state.contrast = _clamp_factor(value)


def set_saturation(state: AdjustmentState, value: float) -> None:
    state.saturation = _clamp_factor(value)


def set_sharpness(state: AdjustmentState, value: float) -> None:
    state.sharpness = _clamp_factor(value)


def set_temperature(state: AdjustmentState, value: int) -> None:
    state.temperature = int(max(-100, min(100, value)))


def apply_adjustments(image: Image.Image, state: AdjustmentState) -> Image.Image:
    result = image.convert("RGB")

    if state.brightness != 1.0:
        result = ImageEnhance.Brightness(result).enhance(state.brightness)
    if state.contrast != 1.0:
        result = ImageEnhance.Contrast(result).enhance(state.contrast)
    if state.saturation != 1.0:
        result = ImageEnhance.Color(result).enhance(state.saturation)
    if state.sharpness != 1.0:
        result = ImageEnhance.Sharpness(result).enhance(state.sharpness)
    if state.temperature != 0:
        result = _apply_temperature(result, state.temperature)

    return result


def auto_color_balance(image: Image.Image) -> Image.Image:
    return ImageOps.autocontrast(image.convert("RGB"), cutoff=2)


def _apply_temperature(image: Image.Image, shift: int) -> Image.Image:
    arr = np.array(image, dtype=np.float32)
    factor = (shift / 100.0) * 0.4  # moderate adjustment
    r_gain = 1.0 + factor
    b_gain = 1.0 - factor
    arr[..., 0] = np.clip(arr[..., 0] * r_gain, 0, 255)
    arr[..., 2] = np.clip(arr[..., 2] * b_gain, 0, 255)
    return Image.fromarray(arr.astype(np.uint8), "RGB")
