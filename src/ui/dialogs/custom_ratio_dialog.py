from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QMessageBox


@dataclass(frozen=True)
class RatioSelection:
    width: float
    height: float


class CustomRatioDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Eigene Aspect Ratio")
        self._width_input = QLineEdit()
        self._height_input = QLineEdit()

        layout = QFormLayout(self)
        layout.addRow("Breite", self._width_input)
        layout.addRow("Höhe", self._height_input)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.selection: RatioSelection | None = None

    def _on_accept(self) -> None:
        try:
            width = float(self._width_input.text())
            height = float(self._height_input.text())
        except ValueError:
            QMessageBox.warning(self, "Ungültige Eingabe", "Bitte numerische Werte eingeben.")
            return

        if width <= 0 or height <= 0:
            QMessageBox.warning(self, "Ungültige Eingabe", "Breite und Höhe müssen > 0 sein.")
            return

        self.selection = RatioSelection(width=width, height=height)
        self.accept()
