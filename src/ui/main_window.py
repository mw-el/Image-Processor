from __future__ import annotations

import logging
from fractions import Fraction
from pathlib import Path
from typing import Iterable

from PySide6.QtCore import Qt, QRectF, QTimer
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QAction
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QApplication,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSlider,
    QSizePolicy,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from PIL import Image

from ..core.adjustments import (
    AdjustmentState,
    set_brightness,
    set_contrast,
    set_saturation,
    set_sharpness,
    set_temperature,
    apply_adjustments,
    auto_color_balance,
)
from ..core.image_store import ImageStore, ImageState
from ..core.crop_service import compute_crop_box, perform_crop, CropServiceError
from ..core.image_processing import ProcessingPipeline, ProcessingError, ProcessingConfig
from ..core.export_service import ExportService, ExportServiceError, ExportConfig, ExportVariant
from ..core.settings import AppSettings
from .dialogs.custom_ratio_dialog import CustomRatioDialog
from .views.image_canvas import ImageCanvas

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"}


class MainWindow(QMainWindow):
    """
    Basic application shell: menu, toolbar, drag & drop and placeholder canvas.
    Subsequent phases will replace the label with the actual image canvas.
    """

    def __init__(self, settings: AppSettings, initial_path: Path | None = None) -> None:
        super().__init__()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.image_store = ImageStore()
        self.settings = settings
        self._initial_path = initial_path
        self.processing_pipeline = ProcessingPipeline(
            ProcessingConfig(
                sharpen_radius=settings.processing.sharpen_radius,
                sharpen_percent=settings.processing.sharpen_percent,
                sharpen_threshold=settings.processing.sharpen_threshold,
                resample_method=settings.processing.resample_method,
            )
        )
        self.export_service = ExportService(
            ExportConfig(
                format=settings.export.format,
                quality=settings.export.quality,
                method=settings.export.method,
            )
        )
        self.has_ratio_selection = False
        self.active_ratio_button: QPushButton | None = None
        self.current_ratio_label_text: str | None = None
        self.current_ratio_value: float | None = None
        self.custom_ratio_tuple: tuple[float, float] | None = None
        self.custom_ratio_button: QPushButton | None = None
        self.current_image_path: Path | None = None
        self.original_image: Image.Image | None = None
        self.base_image: Image.Image | None = None
        self.current_adjusted_image: Image.Image | None = None
        self.adjustment_state = AdjustmentState()
        self.metadata_text = ""
        self.metadata_dirty = False

        self.setWindowTitle("AA Image Processor")
        self.resize(1280, 900)
        self.setAcceptDrops(True)

        self._create_actions()
        self._create_menus()
        self._create_toolbar()
        self._create_central_widget()

    # --- UI creation helpers -------------------------------------------------
    def _create_actions(self) -> None:
        self.open_action = QAction("Bild öffnen …", self)
        self.open_action.setShortcut("Ctrl+O")
        self.open_action.triggered.connect(self.open_image_dialog)

        self.crop_action = QAction("Ausschnitt übernehmen", self)
        self.crop_action.setShortcut("Ctrl+Shift+C")
        self.crop_action.triggered.connect(self.apply_crop)

        self.save_action = QAction("Änderungen speichern", self)
        self.save_action.setShortcut("Ctrl+S")
        self.save_action.triggered.connect(self.export_variants)
        self.save_action.setEnabled(False)

        self.undo_action = QAction("Rückgängig", self)
        self.undo_action.setShortcut("Ctrl+Z")
        self.undo_action.triggered.connect(self.undo_change)
        self.undo_action.setEnabled(False)

        self.redo_action = QAction("Wiederholen", self)
        self.redo_action.setShortcut("Ctrl+Shift+Z")
        self.redo_action.triggered.connect(self.redo_change)
        self.redo_action.setEnabled(False)

        self.reset_action = QAction("Zurück zum Original", self)
        self.reset_action.setShortcut("Ctrl+R")
        self.reset_action.triggered.connect(self.reset_to_original)
        self.reset_action.setEnabled(False)

        self.exit_action = QAction("Beenden", self)
        self.exit_action.setShortcut("Ctrl+Q")
        self.exit_action.triggered.connect(self.close)

    def _create_menus(self) -> None:
        file_menu = self.menuBar().addMenu("&Datei")
        file_menu.addAction(self.open_action)
        file_menu.addAction(self.save_action)
        file_menu.addSeparator()
        file_menu.addAction(self.exit_action)

        edit_menu = self.menuBar().addMenu("&Bearbeiten")
        edit_menu.addAction(self.undo_action)
        edit_menu.addAction(self.redo_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.reset_action)

    def _create_toolbar(self) -> None:
        toolbar = QToolBar("Hauptwerkzeuge")
        toolbar.setMovable(False)
        toolbar.addAction(self.open_action)
        toolbar.addAction(self.crop_action)
        toolbar.addAction(self.save_action)
        toolbar.addSeparator()
        toolbar.addAction(self.undo_action)
        toolbar.addAction(self.redo_action)
        toolbar.addAction(self.reset_action)
        self.addToolBar(Qt.TopToolBarArea, toolbar)

    def _create_central_widget(self) -> None:
        central = QWidget(self)
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.setSpacing(12)

        self.canvas = ImageCanvas()
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        root_layout.addWidget(self.canvas, stretch=3)

        self.controls_width = 360
        controls_widget = QWidget()
        controls_widget.setFixedWidth(self.controls_width)
        controls_layout = QVBoxLayout(controls_widget)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(6)

        ratio_grid = QGridLayout()
        ratio_grid.setSpacing(6)
        self.ratio_buttons: dict[str, QPushButton] = {}
        ratio_defs = [
            ("1:1", 1 / 1),
            ("2:3", 2 / 3),
            ("3:4", 3 / 4),
            ("9:16", 9 / 16),
            ("?:?", None),
            ("3:2", 3 / 2),
            ("4:3", 4 / 3),
            ("16:9", 16 / 9),
        ]
        for idx, (label, ratio) in enumerate(ratio_defs):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setFixedWidth(int(self.controls_width / 4) - 4)
            btn.setFixedHeight(36)
            btn.setStyleSheet("QPushButton:checked { background-color: #ff7b33; color: #ffffff; }")
            btn.clicked.connect(lambda checked, b=btn, lbl=label, r=ratio: self._ratio_button_clicked(b, lbl, r))
            row = idx // 4
            col = idx % 4
            ratio_grid.addWidget(btn, row, col)
            self.ratio_buttons[label] = btn
            if label == "?:?":
                self.custom_ratio_button = btn

        controls_layout.addLayout(ratio_grid)

        adjustments_layout = QVBoxLayout()
        adjustments_layout.setSpacing(4)
        self.adjustment_controls: list[QWidget] = []

        self.brightness_slider, self.brightness_label = self._create_slider_control(
            adjustments_layout,
            "Helligkeit",
            20,
            200,
            100,
            self._on_brightness_change,
            lambda: self._commit_current_state("Helligkeit angepasst"),
        )
        self.contrast_slider, self.contrast_label = self._create_slider_control(
            adjustments_layout,
            "Kontrast",
            20,
            200,
            100,
            self._on_contrast_change,
            lambda: self._commit_current_state("Kontrast angepasst"),
        )
        self.saturation_slider, self.saturation_label = self._create_slider_control(
            adjustments_layout,
            "Sättigung",
            20,
            200,
            100,
            self._on_saturation_change,
            lambda: self._commit_current_state("Sättigung angepasst"),
        )
        self.sharpness_slider, self.sharpness_label = self._create_slider_control(
            adjustments_layout,
            "Schärfe",
            20,
            200,
            100,
            self._on_sharpness_change,
            lambda: self._commit_current_state("Schärfe angepasst"),
        )

        temp_container = QVBoxLayout()
        self.temperature_label = QLabel("Temperatur: 0")
        temp_container.addWidget(self.temperature_label)
        self.temperature_slider = QSlider(Qt.Horizontal)
        self.temperature_slider.setRange(-100, 100)
        self.temperature_slider.setValue(0)
        self.temperature_slider.valueChanged.connect(self._temperature_changed)
        self.temperature_slider.sliderReleased.connect(self._commit_temperature_state)
        temp_container.addWidget(self.temperature_slider)
        adjustments_layout.addLayout(temp_container)
        self.adjustment_controls.extend([self.temperature_label, self.temperature_slider])

        controls_layout.addLayout(adjustments_layout)

        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(8)
        button_width = int((self.controls_width - 2 * buttons_row.spacing()) / 3) - 4

        self.save_changes_btn = QPushButton("Speichern")
        self.save_changes_btn.setToolTip("Aktuelle Varianten exportieren")
        self.save_changes_btn.clicked.connect(self.export_variants)
        self.save_changes_btn.setFixedWidth(button_width)
        buttons_row.addWidget(self.save_changes_btn)
        self.adjustment_controls.append(self.save_changes_btn)

        self.auto_balance_btn = QPushButton("Farbe")
        self.auto_balance_btn.setToolTip("Automatische Farbbalance anwenden")
        self.auto_balance_btn.clicked.connect(self._auto_color_balance)
        self.auto_balance_btn.setFixedWidth(button_width)
        buttons_row.addWidget(self.auto_balance_btn)
        self.adjustment_controls.append(self.auto_balance_btn)

        self.reset_sliders_btn = QPushButton("Reset")
        self.reset_sliders_btn.setToolTip("Alle Regler auf Standardwerte zurücksetzen")
        self.reset_sliders_btn.clicked.connect(self._reset_sliders_clicked)
        self.reset_sliders_btn.setFixedWidth(button_width)
        buttons_row.addWidget(self.reset_sliders_btn)
        self.adjustment_controls.append(self.reset_sliders_btn)

        controls_layout.addLayout(buttons_row)

        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        controls_layout.addWidget(separator)

        metadata_layout = QVBoxLayout()
        metadata_layout.setSpacing(2)
        self.metadata_name_label = QLabel("Datei: -")
        self.metadata_resolution_label = QLabel("Auflösung: -")
        metadata_layout.addWidget(self.metadata_name_label)
        metadata_layout.addWidget(self.metadata_resolution_label)
        self.metadata_edit = QPlainTextEdit()
        self.metadata_edit.setPlaceholderText("Metadaten im Format key=value pro Zeile")
        self.metadata_edit.setFixedHeight(140)
        self.metadata_edit.textChanged.connect(self._metadata_changed)
        metadata_layout.addWidget(self.metadata_edit)
        controls_layout.addLayout(metadata_layout)

        self.status_log = QPlainTextEdit()
        self.status_log.setReadOnly(True)
        self.status_log.setMinimumHeight(100)
        self.status_log.setPlaceholderText("Statusmeldungen…")
        controls_layout.addWidget(self.status_log)

        root_layout.addWidget(controls_widget, stretch=1)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.setCentralWidget(central)
        self._set_adjustment_controls_enabled(False)
        self._update_history_actions()
        if self._initial_path:
            QTimer.singleShot(0, lambda: self._open_initial_image(self._initial_path))

    # --- File handling -------------------------------------------------------
    def open_image_dialog(self) -> None:
        start_dir = str(Path.home())
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Bild öffnen",
            start_dir,
            "Bilder (*.png *.jpg *.jpeg *.webp *.bmp *.tiff)",
        )

        if file_path:
            self._handle_file_drop(Path(file_path))

    def _handle_file_drop(self, path: Path) -> None:
        if not path.exists():
            self._show_error(f"Datei wurde nicht gefunden:\n{path}")
            return

        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            self._show_error("Das Dateiformat wird derzeit nicht unterstützt.")
            return

        try:
            self.image_store.load(path)
        except Exception as exc:  # fail fast + visible error dialog
            self.logger.exception("Fehler beim Laden von %s", path)
            self._show_error(f"Bild konnte nicht geladen werden:\n{exc}")
            return

        self._reset_internal_state(clear_canvas=False)
        self.current_image_path = path
        try:
            pil_image = Image.open(path).convert("RGB")
        except Exception as exc:
            self._show_error(f"PIL konnte das Bild nicht laden:\n{exc}")
            return
        self.original_image = pil_image
        self.base_image = pil_image.copy()
        self.current_adjusted_image = self.base_image.copy()
        self.canvas.display_pil_image(self.base_image)
        self._reset_adjustments()
        self.metadata_dirty = False
        self._set_adjustment_controls_enabled(True)
        self._enable_save_buttons(True)
        self._update_history_actions()
        self.logger.info("Bild geladen: %s", path)
        self.status_bar.showMessage(f"Aktuelles Bild: {path.name}", 5000)
        self._append_status(f"Geladen: {path}")
        self._load_metadata_info(path)

    def _open_initial_image(self, path: Path) -> None:
        if not path.exists():
            self.status_bar.showMessage(f"Datei nicht gefunden: {path}", 7000)
            return
        self._handle_file_drop(path)

    # --- Drag & drop events --------------------------------------------------
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if self._has_supported_file(event.mimeData().urls()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        urls = event.mimeData().urls()
        if not urls:
            return

        path = Path(urls[0].toLocalFile())
        self._handle_file_drop(path)
        event.acceptProposedAction()

    # --- Helpers -------------------------------------------------------------
    def _has_supported_file(self, urls: Iterable) -> bool:
        for url in urls or []:
            if Path(url.toLocalFile()).suffix.lower() in SUPPORTED_EXTENSIONS:
                return True
        return False

    def _show_error(self, message: str) -> None:
        QMessageBox.critical(self, "Fehler", message)
        self.status_bar.showMessage(message, 5000)

    # --- Ratio handling ------------------------------------------------------
    def _apply_ratio(self, ratio: float) -> None:
        if not self.image_store.current:
            self._show_error("Bitte zuerst ein Bild laden.")
            return
        self.current_ratio_value = ratio
        rect = self.canvas.rect()
        centered_rect = self._compute_centered_rect(rect, ratio)
        self.canvas.crop_overlay.set_selection(centered_rect, ratio)
        self.has_ratio_selection = True
        self.logger.info("Aspect Ratio gesetzt: %.4f", ratio)

    def _compute_centered_rect(self, bounds, ratio: float):
        width = bounds.width()
        height = width / ratio
        if height > bounds.height():
            height = bounds.height()
            width = height * ratio
        x = bounds.center().x() - width / 2
        y = bounds.center().y() - height / 2
        return QRectF(x, y, width, height)

    def _ratio_button_clicked(self, button: QPushButton, label: str, ratio: float | None) -> None:
        if button is self.active_ratio_button:
            button.setChecked(False)
            self.active_ratio_button = None
            self.canvas.crop_overlay.clear_selection()
            self.has_ratio_selection = False
            self.current_ratio_label_text = None
            self.current_ratio_value = None
            self.status_bar.showMessage("Aspect Ratio entfernt", 4000)
            return

        if self.active_ratio_button:
            self.active_ratio_button.setChecked(False)
        self.active_ratio_button = button
        self._enter_crop_mode()
        modifiers = QApplication.keyboardModifiers()
        ratio_value: float | None = None
        label_text = label

        if ratio is None:
            use_stored = self.custom_ratio_tuple and not (modifiers & Qt.ShiftModifier)
            if use_stored and self.custom_ratio_tuple:
                width, height = self.custom_ratio_tuple
                ratio_value = width / height if height else 1.0
                label_text = f"{int(width)}:{int(height)}"
            else:
                dialog = CustomRatioDialog(self)
                if dialog.exec() == dialog.Accepted and dialog.selection:
                    width = dialog.selection.width
                    height = dialog.selection.height
                    self.custom_ratio_tuple = (width, height)
                    ratio_value = width / height if height else 1.0
                    label_text = f"{int(width)}:{int(height)}"
                    if self.custom_ratio_button:
                        self.custom_ratio_button.setText(label_text)
                else:
                    button.setChecked(False)
                    self.active_ratio_button = None
                    return
        else:
            ratio_value = ratio

        self.current_ratio_label_text = label_text
        self.current_ratio_value = ratio_value
        self._apply_ratio(ratio_value)
        button.setChecked(True)
        self.has_ratio_selection = True

    def _enter_crop_mode(self) -> None:
        if not getattr(self, "original_image", None):
            return
        self.base_image = self.original_image.copy()
        self.current_adjusted_image = None
        self._append_status("Crop-Modus aktiviert")

    def apply_crop(self) -> None:
        selection = self.canvas.crop_overlay.current_selection()
        pixmap = self.canvas.current_pixmap()
        if not self.image_store.current or not selection or pixmap is None:
            self._show_error("Bitte Bild laden und Aspect Ratio auswählen.")
            return
        if not self.has_ratio_selection:
            self._show_error("Bitte zuerst ein Aspect Ratio auswählen.")
            return

        try:
            crop_box = compute_crop_box(selection.rect, QRectF(self.canvas.rect()), pixmap)
            cropped_image = perform_crop(pixmap, crop_box)
        except CropServiceError as exc:
            self._show_error(str(exc))
            return

        self.base_image = cropped_image
        self._reset_adjustments()
        self._set_adjustment_controls_enabled(True)
        self._render_adjusted_image()
        self._set_adjustment_controls_enabled(True)
        self._enable_save_buttons(True)
        self._commit_current_state(f"Crop {selection.aspect_ratio:.2f}")
        self.status_bar.showMessage("Ausschnitt angewendet", 5000)
        self._append_status(f"Ausschnitt angewendet ({self.current_ratio_label_text or 'n/a'})")

    # --- Adjustments --------------------------------------------------------
    def _render_adjusted_image(self) -> None:
        if not self.base_image:
            return
        try:
            adjusted = apply_adjustments(self.base_image, self.adjustment_state)
        except ProcessingError as exc:
            self._show_error(str(exc))
            return

        self.current_adjusted_image = adjusted
        self.canvas.display_pil_image(adjusted)
        self._enable_save_buttons(True)

    def _commit_current_state(self, description: str) -> None:
        if not self.current_adjusted_image:
            return
        self._push_state(description, self.current_adjusted_image)

    def _push_state(self, description: str, image: Image.Image) -> None:
        if not self.image_store.current:
            return
        self.image_store.push_state(
            ImageState(
                path=self.image_store.current.path,
                description=description,
                payload={
                    "base_image": self.base_image.copy() if self.base_image else None,
                    "adjustment_state": {
                        "brightness": self.adjustment_state.brightness,
                        "contrast": self.adjustment_state.contrast,
                        "saturation": self.adjustment_state.saturation,
                        "sharpness": self.adjustment_state.sharpness,
                        "temperature": self.adjustment_state.temperature,
                    },
                    "current_image": image.copy(),
                    "metadata_text": self.metadata_edit.toPlainText() if hasattr(self, "metadata_edit") else "",
                },
            )
        )
        self._update_history_actions()

    def _on_brightness_change(self, value: int, label: QLabel) -> None:
        factor = self._slider_to_factor(value)
        label.setText(f"Helligkeit: {factor:.2f}")
        set_brightness(self.adjustment_state, factor)
        if self.base_image:
            self._render_adjusted_image()

    def _on_contrast_change(self, value: int, label: QLabel) -> None:
        factor = self._slider_to_factor(value)
        label.setText(f"Kontrast: {factor:.2f}")
        set_contrast(self.adjustment_state, factor)
        if self.base_image:
            self._render_adjusted_image()

    def _on_saturation_change(self, value: int, label: QLabel) -> None:
        factor = self._slider_to_factor(value)
        label.setText(f"Sättigung: {factor:.2f}")
        set_saturation(self.adjustment_state, factor)
        if self.base_image:
            self._render_adjusted_image()

    def _on_sharpness_change(self, value: int, label: QLabel) -> None:
        factor = self._slider_to_factor(value)
        label.setText(f"Schärfe: {factor:.2f}")
        set_sharpness(self.adjustment_state, factor)
        if self.base_image:
            self._render_adjusted_image()

    def _temperature_changed(self, value: int) -> None:
        self.temperature_label.setText(f"Temperatur: {value}")
        set_temperature(self.adjustment_state, value)
        if self.base_image:
            self._render_adjusted_image()

    def _commit_temperature_state(self) -> None:
        if not self.base_image:
            return
        self._commit_current_state("Temperatur angepasst")

    def _auto_color_balance(self) -> None:
        if not self.base_image:
            self._show_error("Bitte zuerst einen Ausschnitt erzeugen.")
            return
        self.base_image = auto_color_balance(self.base_image)
        self._render_adjusted_image()
        self._commit_current_state("Auto-Farbbalance")

    def _reset_adjustments(self) -> None:
        self.adjustment_state = AdjustmentState()
        self._sync_all_sliders()

    def _reset_sliders_clicked(self) -> None:
        if not self.base_image:
            self._show_error("Bitte zuerst einen Ausschnitt erzeugen.")
            return
        self._reset_adjustments()
        self._render_adjusted_image()
        self._commit_current_state("Einstellungen zurückgesetzt")

    def _sync_temperature_slider(self, value: int) -> None:
        if hasattr(self, "temperature_slider"):
            self.temperature_slider.blockSignals(True)
            self.temperature_slider.setValue(value)
            self.temperature_slider.blockSignals(False)
            self.temperature_label.setText(f"Temperatur: {value}")

    def _set_adjustment_controls_enabled(self, enabled: bool) -> None:
        for widget in getattr(self, "adjustment_controls", []):
            widget.setEnabled(enabled)
        self._enable_save_buttons(enabled and self.current_adjusted_image is not None)

    def _enable_save_buttons(self, enabled: bool) -> None:
        if hasattr(self, "save_action"):
            self.save_action.setEnabled(enabled)
        if hasattr(self, "save_changes_btn"):
            self.save_changes_btn.setEnabled(enabled)
        if hasattr(self, "auto_balance_btn"):
            self.auto_balance_btn.setEnabled(enabled)
        if hasattr(self, "reset_sliders_btn"):
            self.reset_sliders_btn.setEnabled(enabled)

    def _metadata_changed(self) -> None:
        self.metadata_text = self.metadata_edit.toPlainText()
        self.metadata_dirty = True

    def _load_metadata_info(self, path: Path) -> None:
        if hasattr(self, "metadata_name_label"):
            self.metadata_name_label.setText(f"Datei: {path.name}")
        try:
            with Image.open(path) as img:
                width, height = img.size
                info = {str(k): str(v) for k, v in img.info.items()}
        except Exception:
            width = height = 0
            info = {}
        if hasattr(self, "metadata_resolution_label"):
            self.metadata_resolution_label.setText(f"Auflösung: {width} × {height}")
        metadata_text = "\n".join(f"{k}={v}" for k, v in info.items())
        if hasattr(self, "metadata_edit"):
            self.metadata_edit.blockSignals(True)
            self.metadata_edit.setPlainText(metadata_text)
            self.metadata_edit.blockSignals(False)
        self.metadata_text = metadata_text
        self.metadata_dirty = False

    def _parse_metadata_text(self) -> dict[str, str]:
        text = self.metadata_edit.toPlainText()
        metadata: dict[str, str] = {}
        for line in text.splitlines():
            line = line.strip()
            if not line or "=" not in line:
                continue
            key, value = line.split("=", 1)
            metadata[key.strip()] = value.strip()
        return metadata

    def _metadata_to_xmp(self, metadata: dict[str, str]) -> bytes | None:
        if not metadata:
            return None
        content = "\n".join(f"{k}={v}" for k, v in metadata.items())
        return content.encode("utf-8")

    def _build_variant_specs(self, adjusted: Image.Image) -> tuple[list[tuple[str, int, int]], str]:
        ratio_label = self.current_ratio_label_text
        ratio_value = self.current_ratio_value
        if ratio_value is None or ratio_value <= 0:
            ratio_label, ratio_value = self._derive_ratio_from_image(adjusted)
        if ratio_label is None:
            ratio_label = "default"
        rules = (
            self.settings.export.variant_rules.get(ratio_label)
            or self.settings.export.variant_rules.get("default", [])
        )
        specs: list[tuple[str, int, int]] = []
        for rule in rules:
            width, height = self._resolve_rule_dimensions(rule, adjusted, ratio_value)
            specs.append((rule.prefix, width, height))
        ratio_suffix = ratio_label.replace(":", "x").replace(" ", "").replace("?", "custom")
        return specs, ratio_suffix

    def _append_status(self, message: str) -> None:
        if hasattr(self, "status_log"):
            self.status_log.appendPlainText(message)
            self.status_log.ensureCursorVisible()

    def _reset_internal_state(self, clear_canvas: bool = True) -> None:
        if self.active_ratio_button:
            self.active_ratio_button.setChecked(False)
        self.active_ratio_button = None
        self.has_ratio_selection = False
        self.current_ratio_label_text = None
        self.current_ratio_value = None
        self.custom_ratio_tuple = None
        self.original_image = None
        self.base_image = None
        self.current_adjusted_image = None
        if clear_canvas:
            self.canvas.clear()
        self.canvas.crop_overlay.clear_selection()
        self._reset_adjustments()
        self._set_adjustment_controls_enabled(False)
        self._enable_save_buttons(False)

    def closeEvent(self, event) -> None:
        self._reset_internal_state()
        self._append_status("Anwendung geschlossen.")
        super().closeEvent(event)

    def _derive_ratio_from_image(self, image: Image.Image) -> tuple[str, float]:
        width, height = image.size
        if height == 0:
            return "default", 1.0
        frac = Fraction(width, height).limit_denominator(100)
        return f"{frac.numerator}:{frac.denominator}", width / height

    def _resolve_rule_dimensions(
        self, rule, adjusted: Image.Image, ratio_value: float
    ) -> tuple[int, int]:
        width_value = rule.width
        height_value = rule.height

        def resolve_dimension(
            value, original, *, is_width: bool, other: int | None = None
        ) -> int:
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

        width_auto = isinstance(width_value, str) and width_value.lower() == "auto"
        height_auto = isinstance(height_value, str) and height_value.lower() == "auto"

        if width_auto and height_auto:
            return adjusted.width, adjusted.height

        if width_auto:
            resolved_height = resolve_dimension(
                height_value, adjusted.height, is_width=False
            )
            resolved_width = max(1, int(round(resolved_height * ratio_value)))
        else:
            resolved_width = resolve_dimension(
                width_value, adjusted.width, is_width=True
            )
            if height_auto:
                resolved_height = max(1, int(round(resolved_width / ratio_value)))
            else:
                resolved_height = resolve_dimension(
                    height_value, adjusted.height, is_width=False, other=resolved_width
                )

        return resolved_width, resolved_height

    def _build_variant_specs(self, adjusted: Image.Image) -> tuple[list[tuple[str, int, int]], str]:
        ratio_label = self.current_ratio_label_text
        ratio_value = self.current_ratio_value
        if ratio_value is None:
            ratio_value = adjusted.width / adjusted.height if adjusted.height else 1.0
        if ratio_label is None:
            frac = Fraction(adjusted.width, adjusted.height).limit_denominator(100)
            ratio_label = f"{frac.numerator}:{frac.denominator}"
        ratio_suffix = ratio_label.replace(":", "x").replace(" ", "").replace("?", "custom")

        if ratio_label == "16:9":
            specs = [
                ("__", 3840, 2160),
                ("_", 1920, 1080),
                ("", 1280, 720),
            ]
        elif ratio_label == "9:16":
            specs = [
                ("__", 2160, 3840),
                ("_", 1080, 1920),
                ("", 720, 1280),
            ]
        else:
            specs = [
                ("__", adjusted.width, adjusted.height),
                ("_", 960, max(1, int(round(960 / ratio_value)))),
                ("", 480, max(1, int(round(480 / ratio_value)))),
            ]
        return specs, ratio_suffix

    def _update_history_actions(self) -> None:
        self.undo_action.setEnabled(bool(self.image_store.undo_stack))
        self.redo_action.setEnabled(bool(self.image_store.redo_stack))
        self.reset_action.setEnabled(self.image_store.original is not None)

    # --- History controls ----------------------------------------------------
    def undo_change(self) -> None:
        state = self.image_store.undo()
        if not state or not state.payload:
            self.status_bar.showMessage("Nichts zum Rückgängig machen.", 4000)
            self._update_history_actions()
            return
        self._restore_from_payload(state.payload)
        self.status_bar.showMessage(f"Rückgängig: {state.description}", 4000)
        self._update_history_actions()

    def redo_change(self) -> None:
        state = self.image_store.redo()
        if not state or not state.payload:
            self.status_bar.showMessage("Nichts zum Wiederholen.", 4000)
            self._update_history_actions()
            return
        self._restore_from_payload(state.payload)
        self.status_bar.showMessage(f"Wiederholt: {state.description}", 4000)
        self._update_history_actions()

    def reset_to_original(self) -> None:
        if not self.image_store.original:
            self._show_error("Kein Originalbild geladen.")
            return
        if self._has_unsaved_changes():
            confirm = QMessageBox.question(
                self,
                "Zurück zum Original?",
                "Alle Anpassungen gehen verloren. Fortfahren?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if confirm != QMessageBox.Yes:
                return
        original_path = self.image_store.original.path
        self.image_store.reset_to_original()
        self._handle_file_drop(original_path)
        self.status_bar.showMessage("Auf Original zurückgesetzt.", 5000)

    def _restore_from_payload(self, payload: dict) -> None:
        base = payload.get("base_image")
        if base:
            self.base_image = base.copy()
            self._set_adjustment_controls_enabled(True)
        else:
            self.base_image = None
            self._set_adjustment_controls_enabled(False)

        adj = payload.get("adjustment_state", {})
        self.adjustment_state = AdjustmentState(
            brightness=adj.get("brightness", 1.0),
            contrast=adj.get("contrast", 1.0),
            saturation=adj.get("saturation", 1.0),
            sharpness=adj.get("sharpness", 1.0),
            temperature=adj.get("temperature", 0),
        )
        self._sync_all_sliders()

        current = payload.get("current_image")
        if current:
            self.current_adjusted_image = current.copy()
            self.canvas.display_pil_image(self.current_adjusted_image)
        else:
            self.current_adjusted_image = None
            self.canvas.clear()

        enabled = self.current_adjusted_image is not None
        self._enable_save_buttons(enabled)
        meta_text = payload.get("metadata_text")
        if meta_text is not None and hasattr(self, "metadata_edit"):
            self.metadata_edit.blockSignals(True)
            self.metadata_edit.setPlainText(meta_text)
            self.metadata_edit.blockSignals(False)
            self.metadata_text = meta_text
            self.metadata_dirty = False

    def _has_unsaved_changes(self) -> bool:
        return bool(self.base_image or self.image_store.has_unsaved_changes() or self.metadata_dirty)

    def _create_slider_control(
        self,
        parent_layout: QVBoxLayout,
        title: str,
        min_value: int,
        max_value: int,
        default: int,
        on_change,
        commit_callback,
    ):
        container = QVBoxLayout()
        container.setSpacing(2)
        label = QLabel(f"{title}: 1.00")
        slider = QSlider(Qt.Horizontal)
        slider.setRange(min_value, max_value)
        slider.setValue(default)
        slider.valueChanged.connect(lambda val: on_change(val, label))
        slider.sliderReleased.connect(commit_callback)
        container.addWidget(label)
        container.addWidget(slider)
        parent_layout.addLayout(container)
        self.adjustment_controls.extend([label, slider])
        return slider, label

    def _slider_to_factor(self, slider_value: int) -> float:
        return round(slider_value / 100.0, 2)

    def _factor_to_slider(self, factor: float) -> int:
        return max(20, min(200, int(round(factor * 100))))

    def _sync_all_sliders(self) -> None:
        if hasattr(self, "brightness_slider"):
            self._sync_factor_slider(self.brightness_slider, self.brightness_label, "Helligkeit", self.adjustment_state.brightness)
        if hasattr(self, "contrast_slider"):
            self._sync_factor_slider(self.contrast_slider, self.contrast_label, "Kontrast", self.adjustment_state.contrast)
        if hasattr(self, "saturation_slider"):
            self._sync_factor_slider(self.saturation_slider, self.saturation_label, "Sättigung", self.adjustment_state.saturation)
        if hasattr(self, "sharpness_slider"):
            self._sync_factor_slider(self.sharpness_slider, self.sharpness_label, "Schärfe", self.adjustment_state.sharpness)
        self._sync_temperature_slider(self.adjustment_state.temperature)

    def _sync_factor_slider(self, slider: QSlider, label: QLabel, prefix: str, value: float) -> None:
        slider.blockSignals(True)
        slider.setValue(self._factor_to_slider(value))
        slider.blockSignals(False)
        label.setText(f"{prefix}: {value:.2f}")

    def export_variants(self) -> None:
        if self.current_adjusted_image is None and self.has_ratio_selection:
            self.apply_crop()

        if not self.image_store.current:
            self._show_error("Keine Varianten zum Export vorhanden.")
            return

        adjusted = self.current_adjusted_image or self.base_image
        if adjusted is None:
            self._show_error("Keine Bilddaten zum Speichern.")
            return

        specs, ratio_suffix = self._build_variant_specs(adjusted)
        metadata_dict = self._parse_metadata_text()
        metadata_bytes = self._metadata_to_xmp(metadata_dict)

        variants: list[ExportVariant] = []
        for prefix, target_width, target_height in specs:
            if target_width == adjusted.width and target_height == adjusted.height:
                variant_img = adjusted.copy()
            else:
                variant_img = self.processing_pipeline.resize_with_quality(
                    adjusted, target_width=target_width, target_height=target_height
                )
            variants.append(
                ExportVariant(
                    prefix=prefix,
                    resolution=(variant_img.width, variant_img.height),
                    ratio_suffix=ratio_suffix,
                    image=variant_img,
                )
            )

        try:
            paths = self.export_service.export_variants(self.image_store.current.path, variants, metadata_bytes)
        except ExportServiceError as exc:
            self._show_error(str(exc))
            return

        names = ", ".join(path.name for path in paths)
        self.metadata_dirty = False
        self.status_bar.showMessage(f"Exportiert: {names}", 7000)
        self._append_status("Gespeichert: " + ", ".join(str(p) for p in paths))
