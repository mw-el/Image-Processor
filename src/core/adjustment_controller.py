from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from .adjustments import (
    AdjustmentState,
    set_brightness,
    set_contrast,
    set_saturation,
    set_sharpness,
    set_temperature,
    set_red_balance,
    set_green_balance,
    set_blue_balance,
)


class AdjustmentControllerError(RuntimeError):
    pass


class AdjustmentController:
    """Manages AdjustmentState and notifies listeners about changes."""

    def __init__(self, on_change: Optional[Callable[[AdjustmentState], None]] = None) -> None:
        self._state = AdjustmentState()
        self._listener = on_change

    @property
    def state(self) -> AdjustmentState:
        return self._state

    def set_listener(self, callback: Callable[[AdjustmentState], None]) -> None:
        self._listener = callback

    def reset(self) -> None:
        self._state = AdjustmentState()
        self._emit()

    def set_state(self, state: AdjustmentState) -> None:
        self._state = state
        self._emit()

    def update_factor(self, field: str, value: float) -> None:
        if field == "brightness":
            set_brightness(self._state, value)
        elif field == "contrast":
            set_contrast(self._state, value)
        elif field == "saturation":
            set_saturation(self._state, value)
        elif field == "sharpness":
            set_sharpness(self._state, value)
        else:
            raise AdjustmentControllerError(f"Unbekanntes Feld: {field}")
        self._emit()

    def update_temperature(self, value: int) -> None:
        set_temperature(self._state, value)
        self._emit()

    def update_red_balance(self, value: int) -> None:
        set_red_balance(self._state, value)
        self._emit()

    def update_green_balance(self, value: int) -> None:
        set_green_balance(self._state, value)
        self._emit()

    def update_blue_balance(self, value: int) -> None:
        set_blue_balance(self._state, value)
        self._emit()

    def _emit(self) -> None:
        if self._listener:
            self._listener(self._state)
