from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass
from typing import Optional

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QComboBox,
    QPushButton,
    QFileDialog,
    QLineEdit,
    QGroupBox,
    QFormLayout,
)
from PySide6.QtCore import Qt, QSize, QUrl
import qtawesome as qta


@dataclass
class SaveAsResult:
    """Result from SaveAsDialog."""
    path: Path
    width: int
    height: int
    format: str  # "webp", "png", "jpeg"


class SaveAsDialog(QDialog):
    """
    Dialog for saving with custom resolution and format.

    Maintains aspect ratio from source image or crop selection.
    """

    def __init__(
        self,
        parent=None,
        source_width: int = 1920,
        source_height: int = 1080,
        suggested_path: Path | None = None,
        bookmarks: list[Path] | None = None,
        default_format: str | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Speichern unter...")
        self.setMinimumWidth(400)

        self.source_width = source_width
        self.source_height = source_height
        self.aspect_ratio = source_width / source_height if source_height > 0 else 1.0
        self.result: Optional[SaveAsResult] = None
        self._updating = False

        self.bookmarks = [p for p in bookmarks or [] if p.exists()]

        # Store base path info for filename generation
        base_path = suggested_path or Path.home() / "image.webp"
        self._selected_format = (
            self._format_from_suffix(base_path.suffix)
            or self._normalize_format(default_format)
            or "WebP"
        )
        self._base_dir = base_path.parent
        self._base_name = base_path.stem  # Original filename without extension
        self._initial_path = self._generate_initial_path()

        self._create_ui()

    def _create_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Button styles matching main window
        btn_style = """
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:pressed {
                background-color: #0D47A1;
            }
        """

        # File path section
        path_group = QGroupBox("Speicherort")
        path_layout = QHBoxLayout(path_group)

        # Initial path with resolution and current format
        self.path_edit = QLineEdit(str(self._initial_path))
        self.path_edit.setMinimumWidth(250)
        self.path_edit.editingFinished.connect(self._on_path_edited)
        path_layout.addWidget(self.path_edit)

        browse_btn = QPushButton()
        browse_btn.setIcon(qta.icon("mdi6.folder-open", color="white"))
        browse_btn.setIconSize(QSize(20, 20))
        browse_btn.setFixedSize(36, 36)
        browse_btn.setToolTip("Ziel wählen")
        browse_btn.setStyleSheet(btn_style)
        browse_btn.clicked.connect(self._browse_path)
        path_layout.addWidget(browse_btn)

        layout.addWidget(path_group)

        # Resolution section
        res_group = QGroupBox("Auflösung")
        res_layout = QFormLayout(res_group)

        # Current resolution info
        info_label = QLabel(f"Original: {self.source_width} × {self.source_height}")
        info_label.setStyleSheet("color: gray;")
        res_layout.addRow(info_label)

        # Width
        width_layout = QHBoxLayout()
        self.width_spin = QSpinBox()
        self.width_spin.setRange(16, 16384)
        self.width_spin.setValue(self.source_width)
        self.width_spin.setSuffix(" px")
        self.width_spin.valueChanged.connect(self._on_width_changed)
        width_layout.addWidget(self.width_spin)
        res_layout.addRow("Breite:", width_layout)

        # Height
        height_layout = QHBoxLayout()
        self.height_spin = QSpinBox()
        self.height_spin.setRange(16, 16384)
        self.height_spin.setValue(self.source_height)
        self.height_spin.setSuffix(" px")
        self.height_spin.valueChanged.connect(self._on_height_changed)
        height_layout.addWidget(self.height_spin)
        res_layout.addRow("Höhe:", height_layout)

        # Aspect ratio info
        self.ratio_label = QLabel(f"Seitenverhältnis: {self._format_ratio()}")
        self.ratio_label.setStyleSheet("color: gray; font-style: italic;")
        res_layout.addRow(self.ratio_label)

        layout.addWidget(res_group)

        # Format section
        format_group = QGroupBox("Format")
        format_layout = QFormLayout(format_group)

        self.format_combo = QComboBox()
        self.format_combo.addItems(["WebP", "PNG", "JPEG"])
        self._set_format_combo(self._selected_format)
        self.format_combo.currentTextChanged.connect(self._on_format_changed)
        format_layout.addRow("Bildformat:", self.format_combo)

        layout.addWidget(format_group)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Abbrechen")
        cancel_btn.setMinimumWidth(100)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Speichern")
        save_btn.setMinimumWidth(100)
        save_btn.setStyleSheet(btn_style)
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

    def _format_ratio(self) -> str:
        """Format aspect ratio as readable string."""
        from fractions import Fraction
        try:
            frac = Fraction(self.source_width, self.source_height).limit_denominator(100)
            return f"{frac.numerator}:{frac.denominator}"
        except (ValueError, ZeroDivisionError):
            return f"{self.aspect_ratio:.2f}:1"

    def _normalize_format(self, format_text: str | None) -> str | None:
        """Normalize different format strings/suffixes to combo display text."""
        if not format_text:
            return None
        mapping = {
            "webp": "WebP",
            "png": "PNG",
            "jpeg": "JPEG",
            "jpg": "JPEG",
            ".webp": "WebP",
            ".png": "PNG",
            ".jpeg": "JPEG",
            ".jpg": "JPEG",
        }
        return mapping.get(format_text.lower())

    def _format_from_suffix(self, suffix: str) -> str | None:
        return self._normalize_format(suffix)

    def _extension_for_format(self, format_text: str) -> str:
        return {"WebP": ".webp", "PNG": ".png", "JPEG": ".jpg"}.get(format_text, ".webp")

    def _current_format_text(self) -> str:
        combo = getattr(self, "format_combo", None)
        if combo:
            return combo.currentText()
        return self._selected_format

    def _generate_initial_path(self) -> Path:
        ext = self._extension_for_format(self._selected_format)
        filename = f"{self._base_name}_{self.source_width}x{self.source_height}{ext}"
        return self._base_dir / filename

    def _set_format_combo(self, format_text: str) -> None:
        if not hasattr(self, "format_combo"):
            return
        idx = self.format_combo.findText(format_text, Qt.MatchFixedString)
        if idx != -1:
            self.format_combo.blockSignals(True)
            self.format_combo.setCurrentIndex(idx)
            self.format_combo.blockSignals(False)

    def _generate_filename_with_resolution(self) -> Path:
        """Generate filename including current resolution."""
        width = self.width_spin.value()
        height = self.height_spin.value()
        ext = self._extension_for_format(self._current_format_text())
        filename = f"{self._base_name}_{width}x{height}{ext}"
        return self._base_dir / filename

    def _update_path_with_resolution(self) -> None:
        """Update the path field with current resolution."""
        new_path = self._generate_filename_with_resolution()
        self.path_edit.setText(str(new_path))

    def _on_width_changed(self, value: int) -> None:
        """Update height to maintain aspect ratio."""
        if self._updating:
            return
        self._updating = True
        new_height = int(round(value / self.aspect_ratio))
        new_height = max(16, min(16384, new_height))
        self.height_spin.setValue(new_height)
        self._update_path_with_resolution()
        self._updating = False

    def _on_height_changed(self, value: int) -> None:
        """Update width to maintain aspect ratio."""
        if self._updating:
            return
        self._updating = True
        new_width = int(round(value * self.aspect_ratio))
        new_width = max(16, min(16384, new_width))
        self.width_spin.setValue(new_width)
        self._update_path_with_resolution()
        self._updating = False

    def _on_format_changed(self, format_text: str) -> None:
        """Update file extension when format changes."""
        self._selected_format = format_text
        self._update_path_with_resolution()

    def _browse_path(self) -> None:
        """Open file dialog to select save path."""
        current_format = self._current_format_text()
        filter_map = {
            "WebP": "WebP Bilder (*.webp)",
            "PNG": "PNG Bilder (*.png)",
            "JPEG": "JPEG Bilder (*.jpg *.jpeg)",
        }
        file_filter = filter_map.get(current_format, "Alle Bilder (*.*)")
        start_dir = Path(self.path_edit.text()).parent if self.path_edit.text() else self._base_dir

        dialog = QFileDialog(
            self,
            "Speichern unter",
            str(start_dir),
            file_filter,
        )
        dialog.setAcceptMode(QFileDialog.AcceptSave)
        dialog.setFileMode(QFileDialog.AnyFile)
        dialog.setOptions(QFileDialog.DontUseNativeDialog)

        for bookmark in self.bookmarks:
            dialog.setSidebarUrls(dialog.sidebarUrls() + [QUrl.fromLocalFile(str(bookmark))])

        # Preselect current suggestion
        dialog.selectFile(str(self._generate_filename_with_resolution()))

        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_files = dialog.selectedFiles()
            if selected_files:
                self._apply_selected_path(Path(selected_files[0]))

    def _on_path_edited(self) -> None:
        """Update defaults when the user edits the path manually."""
        path_text = self.path_edit.text().strip()
        if not path_text:
            return
        self._apply_selected_path(Path(path_text))

    def _apply_selected_path(self, path: Path) -> None:
        """Update base dir/name and format based on selected path."""
        detected_format = self._format_from_suffix(path.suffix)
        if detected_format:
            self._selected_format = detected_format
            self._set_format_combo(detected_format)

        if path.suffix:
            path = path.with_suffix(self._extension_for_format(self._current_format_text()))

        self._base_dir = path.parent
        self._base_name = path.stem
        self._update_path_with_resolution()

    def _on_save(self) -> None:
        """Validate and accept dialog."""
        from PySide6.QtWidgets import QMessageBox

        try:
            path_text = self.path_edit.text().strip()

            if not path_text:
                QMessageBox.warning(self, "Fehler", "Bitte einen Dateinamen eingeben.")
                return

            path = Path(path_text)

            # Ensure correct extension
            format_text = self.format_combo.currentText().lower()
            ext_map = {"webp": ".webp", "png": ".png", "jpeg": ".jpg"}
            expected_ext = ext_map.get(format_text, ".webp")

            if path.suffix.lower() not in [expected_ext, ".jpeg" if format_text == "jpeg" else expected_ext]:
                path = path.with_suffix(expected_ext)

            self.result = SaveAsResult(
                path=path,
                width=self.width_spin.value(),
                height=self.height_spin.value(),
                format=format_text,
            )
            self.accept()

        except Exception as exc:
            QMessageBox.critical(self, "Fehler", f"Fehler beim Validieren des Pfads: {exc}")
