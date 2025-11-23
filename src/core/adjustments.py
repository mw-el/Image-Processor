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
    red_balance: int = 0  # -100 .. 100
    green_balance: int = 0  # -100 .. 100
    blue_balance: int = 0  # -100 .. 100


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


def set_red_balance(state: AdjustmentState, value: int) -> None:
    state.red_balance = int(max(-100, min(100, value)))


def set_green_balance(state: AdjustmentState, value: int) -> None:
    state.green_balance = int(max(-100, min(100, value)))


def set_blue_balance(state: AdjustmentState, value: int) -> None:
    state.blue_balance = int(max(-100, min(100, value)))


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
    if state.red_balance != 0 or state.green_balance != 0 or state.blue_balance != 0:
        result = _apply_rgb_balance(result, state.red_balance, state.green_balance, state.blue_balance)

    return result


def calculate_auto_balance_photoshop_style(image: Image.Image) -> AdjustmentState:
    """
    Photoshop-style auto balance using histogram clipping.
    Clips darkest 2% and brightest 2% per channel, then stretches.
    """
    rgb_image = image.convert("RGB")
    arr = np.array(rgb_image, dtype=np.float32)

    brightness = 1.0
    contrast = 1.0
    r_balance = 0
    g_balance = 0
    b_balance = 0

    # Analyze each channel
    for ch_idx, (r_ch, g_ch, b_ch) in enumerate([(arr[..., 0], 0, 0), (arr[..., 1], 1, 1), (arr[..., 2], 2, 2)]):
        if ch_idx > 0:
            continue  # Only do overall analysis once

        # Find 2nd and 98th percentile for full image
        p2 = np.percentile(arr, 2)
        p98 = np.percentile(arr, 98)

        # Calculate how much to stretch
        current_range = p98 - p2
        if current_range > 10:  # Avoid division by zero
            # How much of the full range (0-255) is used?
            used_ratio = current_range / 255.0

            # If less than 85% of range is used, stretch it (more aggressive)
            if used_ratio < 0.85:
                # Contrast boost to stretch histogram
                contrast = 1.0 / used_ratio
                contrast = np.clip(contrast, 1.0, 1.5)  # Max 50% increase

                # Brightness adjustment to re-center
                target_mid = 127.5
                current_mid = (p2 + p98) / 2.0
                brightness = target_mid / current_mid if current_mid > 10 else 1.0
                brightness = np.clip(brightness, 0.75, 1.35)  # Max ±25-35%

    # Color balance per channel
    r_p2, r_p98 = np.percentile(arr[..., 0], 2), np.percentile(arr[..., 0], 98)
    g_p2, g_p98 = np.percentile(arr[..., 1], 2), np.percentile(arr[..., 1], 98)
    b_p2, b_p98 = np.percentile(arr[..., 2], 2), np.percentile(arr[..., 2], 98)

    r_mid = (r_p2 + r_p98) / 2.0
    g_mid = (g_p2 + g_p98) / 2.0
    b_mid = (b_p2 + b_p98) / 2.0
    avg_mid = (r_mid + g_mid + b_mid) / 3.0

    if avg_mid > 10:
        r_balance = int(np.clip((avg_mid - r_mid) / avg_mid * 80, -40, 40))
        g_balance = int(np.clip((avg_mid - g_mid) / avg_mid * 80, -40, 40))
        b_balance = int(np.clip((avg_mid - b_mid) / avg_mid * 80, -40, 40))

    return AdjustmentState(
        brightness=round(brightness, 2),
        contrast=round(contrast, 2),
        saturation=1.0,
        sharpness=1.0,
        temperature=0,
        red_balance=r_balance,
        green_balance=g_balance,
        blue_balance=b_balance,
    )


def calculate_auto_balance_conservative(image: Image.Image) -> AdjustmentState:
    """
    Conservative auto balance: only adjust if histogram is clearly compressed.
    Maximum adjustment: ±20-30%
    """
    rgb_image = image.convert("RGB")
    arr = np.array(rgb_image, dtype=np.float32)

    brightness = 1.0
    contrast = 1.0

    # Check if histogram is compressed
    p5 = np.percentile(arr, 5)
    p95 = np.percentile(arr, 95)
    current_range = p95 - p5

    # Only adjust if not using full range (threshold erhöht von 180 auf 210)
    if current_range < 210:  # Less than ~82% of full range
        # Gentle stretch
        contrast = min(210.0 / current_range, 1.3)  # Max 30% increase

        # Brightness adjustment if needed
        current_mid = (p5 + p95) / 2.0
        if current_mid < 115:
            brightness = min(125.0 / current_mid, 1.25)  # Max +25%
        elif current_mid > 140:
            brightness = max(130.0 / current_mid, 0.8)  # Max -20%

    return AdjustmentState(
        brightness=round(brightness, 2),
        contrast=round(contrast, 2),
        saturation=1.0,
        sharpness=1.0,
        temperature=0,
        red_balance=0,
        green_balance=0,
        blue_balance=0,
    )


def calculate_auto_balance_color_only(image: Image.Image) -> AdjustmentState:
    """
    Color balance only: adjust RGB channels to neutralize color casts.
    No brightness or contrast changes.
    """
    rgb_image = image.convert("RGB")
    arr = np.array(rgb_image, dtype=np.float32)

    # Use median instead of mean to avoid outlier influence
    r_median = np.median(arr[..., 0])
    g_median = np.median(arr[..., 1])
    b_median = np.median(arr[..., 2])

    avg_median = (r_median + g_median + b_median) / 3.0

    r_balance = 0
    g_balance = 0
    b_balance = 0

    if avg_median > 10:
        # Calculate deviation and apply stronger correction
        r_dev = (avg_median - r_median) / avg_median * 100.0
        g_dev = (avg_median - g_median) / avg_median * 100.0
        b_dev = (avg_median - b_median) / avg_median * 100.0

        # Correct color casts (>1.5% threshold, stärkere Korrektur)
        if abs(r_dev) > 1.5:
            r_balance = int(np.clip(r_dev * 0.85, -45, 45))
        if abs(g_dev) > 1.5:
            g_balance = int(np.clip(g_dev * 0.85, -45, 45))
        if abs(b_dev) > 1.5:
            b_balance = int(np.clip(b_dev * 0.85, -45, 45))

    return AdjustmentState(
        brightness=1.0,
        contrast=1.0,
        saturation=1.0,
        sharpness=1.0,
        temperature=0,
        red_balance=r_balance,
        green_balance=g_balance,
        blue_balance=b_balance,
    )


def _apply_temperature(image: Image.Image, shift: int) -> Image.Image:
    arr = np.array(image, dtype=np.float32)
    factor = (shift / 100.0) * 0.4  # moderate adjustment
    r_gain = 1.0 + factor
    b_gain = 1.0 - factor
    arr[..., 0] = np.clip(arr[..., 0] * r_gain, 0, 255)
    arr[..., 2] = np.clip(arr[..., 2] * b_gain, 0, 255)
    return Image.fromarray(arr.astype(np.uint8), "RGB")


def _apply_rgb_balance(image: Image.Image, red: int, green: int, blue: int) -> Image.Image:
    """Apply individual RGB channel adjustments (-100 to +100)."""
    arr = np.array(image, dtype=np.float32)

    # Convert -100..100 to gain factors (0.6 to 1.4 range)
    r_gain = 1.0 + (red / 100.0) * 0.4
    g_gain = 1.0 + (green / 100.0) * 0.4
    b_gain = 1.0 + (blue / 100.0) * 0.4

    arr[..., 0] = np.clip(arr[..., 0] * r_gain, 0, 255)
    arr[..., 1] = np.clip(arr[..., 1] * g_gain, 0, 255)
    arr[..., 2] = np.clip(arr[..., 2] * b_gain, 0, 255)

    return Image.fromarray(arr.astype(np.uint8), "RGB")
