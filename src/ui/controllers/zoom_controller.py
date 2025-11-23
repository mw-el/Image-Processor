from __future__ import annotations

from PySide6.QtWidgets import QLabel, QSlider

from ..views.image_canvas import ImageCanvas


class ZoomController:
    """
    Couples zoom slider/label with the ImageCanvas so zoom behaviour stays out of the MainWindow.
    """

    def __init__(self, canvas: ImageCanvas, slider: QSlider, label: QLabel) -> None:
        self.canvas = canvas
        self.slider = slider
        self.label = label
        self.slider.valueChanged.connect(self._on_slider_value_changed)
        self._sync_label(self.slider.value())

    def _on_slider_value_changed(self, value: int) -> None:
        factor = max(10, min(200, value)) / 100.0
        self.canvas.set_zoom_factor(factor)
        self._sync_label(value)

    def reset(self) -> None:
        self.slider.blockSignals(True)
        self.slider.setValue(100)
        self.slider.blockSignals(False)
        self.canvas.set_zoom_factor(1.0)
        self._sync_label(100)

    def set_enabled(self, enabled: bool) -> None:
        self.slider.setEnabled(enabled)
        self.label.setEnabled(enabled)

    def _sync_label(self, slider_value: int) -> None:
        self.label.setText(f"Zoom: {slider_value}%")

