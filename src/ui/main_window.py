from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable

from PySide6.QtCore import Qt, QRectF, QTimer
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QAction
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
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
    adjust_contrast,
    adjust_saturation,
    set_temperature,
    apply_adjustments,
    auto_color_balance,
)
from ..core.image_store import ImageStore, ImageState
from ..core.crop_service import compute_crop_box, perform_crop, CropServiceError
from ..core.image_processing import ProcessingPipeline, ProcessingError, ProcessingConfig
from ..core.export_service import ExportService, ExportServiceError, ExportConfig
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
        self.latest_variants: dict[str, Image.Image] = {}
        self.export_service = ExportService(
            ExportConfig(
                max_prefix=settings.export.max_prefix,
                medium_prefix=settings.export.medium_prefix,
                small_prefix=settings.export.small_prefix,
                medium_width=settings.export.medium_width,
                small_width=settings.export.small_width,
                format=settings.export.format,
                quality=settings.export.quality,
                method=settings.export.method,
            )
        )
        self.base_image: Image.Image | None = None
        self.current_adjusted_image: Image.Image | None = None
        self.adjustment_state = AdjustmentState()

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
        layout = QVBoxLayout(central)
        layout.setContentsMargins(12, 12, 12, 12)

        ratios_layout = QHBoxLayout()
        ratios_layout.setSpacing(8)
        self.ratio_buttons: dict[str, QPushButton] = {}
        for label, ratio in self._ratio_definitions():
            button = QPushButton(label)
            button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            button.clicked.connect(lambda _, r=ratio: self._apply_ratio(r))
            ratios_layout.addWidget(button)
            self.ratio_buttons[label] = button

        custom_button = QPushButton("Eigene Ratio …")
        custom_button.clicked.connect(self._open_custom_ratio_dialog)
        ratios_layout.addWidget(custom_button)

        layout.addLayout(ratios_layout)

        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(8)
        self.adjustment_controls: list[QWidget] = []

        def add_control(widget: QWidget) -> None:
            controls_layout.addWidget(widget)
            self.adjustment_controls.append(widget)

        self.contrast_minus_btn = QPushButton("Kontrast -")
        self.contrast_minus_btn.clicked.connect(lambda: self._change_contrast(-0.1))
        add_control(self.contrast_minus_btn)

        self.contrast_plus_btn = QPushButton("Kontrast +")
        self.contrast_plus_btn.clicked.connect(lambda: self._change_contrast(0.1))
        add_control(self.contrast_plus_btn)

        self.saturation_minus_btn = QPushButton("Sättigung -")
        self.saturation_minus_btn.clicked.connect(lambda: self._change_saturation(-0.1))
        add_control(self.saturation_minus_btn)

        self.saturation_plus_btn = QPushButton("Sättigung +")
        self.saturation_plus_btn.clicked.connect(lambda: self._change_saturation(0.1))
        add_control(self.saturation_plus_btn)

        self.auto_balance_btn = QPushButton("Auto-Farbbalance")
        self.auto_balance_btn.clicked.connect(self._auto_color_balance)
        add_control(self.auto_balance_btn)

        self.temperature_label = QLabel("Temperatur: 0")
        add_control(self.temperature_label)

        self.temperature_slider = QSlider(Qt.Horizontal)
        self.temperature_slider.setRange(-100, 100)
        self.temperature_slider.setValue(0)
        self.temperature_slider.valueChanged.connect(self._temperature_changed)
        self.temperature_slider.sliderReleased.connect(self._commit_temperature_state)
        add_control(self.temperature_slider)

        self.save_changes_btn = QPushButton("Änderungen speichern")
        self.save_changes_btn.clicked.connect(self.export_variants)
        add_control(self.save_changes_btn)

        layout.addLayout(controls_layout)

        self.canvas = ImageCanvas()
        layout.addWidget(self.canvas, stretch=1)

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

        try:
            self.canvas.load_image(path)
        except ValueError as exc:
            self._show_error(str(exc))
            return

        self.base_image = None
        self.current_adjusted_image = None
        self.adjustment_state = AdjustmentState()
        self.latest_variants = {}
        self._set_adjustment_controls_enabled(False)
        self.export_action.setEnabled(False)
        self._update_history_actions()
        self.logger.info("Bild geladen: %s", path)
        self.status_bar.showMessage(f"Aktuelles Bild: {path.name}", 5000)

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
    def _ratio_definitions(self) -> list[tuple[str, float]]:
        return [
            ("1:1", 1 / 1),
            ("2:3", 2 / 3),
            ("3:4", 3 / 4),
            ("16:9", 16 / 9),
            ("3:2", 3 / 2),
            ("4:3", 4 / 3),
            ("9:16", 9 / 16),
        ]

    def _apply_ratio(self, ratio: float) -> None:
        if not self.image_store.current:
            self._show_error("Bitte zuerst ein Bild laden.")
            return
        rect = self.canvas.rect()
        centered_rect = self._compute_centered_rect(rect, ratio)
        self.canvas.crop_overlay.set_selection(centered_rect, ratio)
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

    def _open_custom_ratio_dialog(self) -> None:
        dialog = CustomRatioDialog(self)
        if dialog.exec() == dialog.Accepted and dialog.selection:
            ratio = dialog.selection.width / dialog.selection.height
            self._apply_ratio(ratio)

    def apply_crop(self) -> None:
        selection = self.canvas.crop_overlay.current_selection()
        pixmap = self.canvas.current_pixmap()
        if not self.image_store.current or not selection or pixmap is None:
            self._show_error("Bitte Bild laden und Aspect Ratio auswählen.")
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
        self._commit_current_state(f"Crop {selection.aspect_ratio:.2f}")
        self.status_bar.showMessage("Ausschnitt angewendet", 5000)

    # --- Adjustments --------------------------------------------------------
    def _render_adjusted_image(self) -> None:
        if not self.base_image:
            return
        try:
            adjusted = apply_adjustments(self.base_image, self.adjustment_state)
            variants = self.processing_pipeline.generate_variants(
                adjusted, self._target_variant_widths()
            )
        except ProcessingError as exc:
            self._show_error(str(exc))
            return

        self.current_adjusted_image = adjusted
        self.canvas.display_pil_image(adjusted)
        self._update_variants(adjusted, variants)

    def _update_variants(self, adjusted: Image.Image, variants) -> None:
        self.latest_variants = {"max": adjusted.copy()}
        for variant in variants:
            self.latest_variants[str(variant.width)] = variant.image.copy()
        self.export_action.setEnabled(True)

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
                        "contrast": self.adjustment_state.contrast,
                        "saturation": self.adjustment_state.saturation,
                        "temperature": self.adjustment_state.temperature,
                    },
                    "current_image": image.copy(),
                    "variants": {k: v.copy() for k, v in self.latest_variants.items()},
                },
            )
        )
        self._update_history_actions()

    def _change_contrast(self, delta: float) -> None:
        if not self.base_image:
            self._show_error("Bitte zuerst einen Ausschnitt erzeugen.")
            return
        adjust_contrast(self.adjustment_state, delta)
        self._render_adjusted_image()
        self._commit_current_state("Kontrast angepasst")

    def _change_saturation(self, delta: float) -> None:
        if not self.base_image:
            self._show_error("Bitte zuerst einen Ausschnitt erzeugen.")
            return
        adjust_saturation(self.adjustment_state, delta)
        self._render_adjusted_image()
        self._commit_current_state("Sättigung angepasst")

    def _temperature_changed(self, value: int) -> None:
        self.temperature_label.setText(f"Temperatur: {value}")
        if not self.base_image:
            return
        set_temperature(self.adjustment_state, value)
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
        self._sync_temperature_slider(0)

    def _sync_temperature_slider(self, value: int) -> None:
        if hasattr(self, "temperature_slider"):
            self.temperature_slider.blockSignals(True)
            self.temperature_slider.setValue(value)
            self.temperature_slider.blockSignals(False)
            self.temperature_label.setText(f"Temperatur: {value}")

    def _set_adjustment_controls_enabled(self, enabled: bool) -> None:
        for widget in getattr(self, "adjustment_controls", []):
            widget.setEnabled(enabled)

    def _target_variant_widths(self) -> list[int]:
        widths = set(self.settings.processing.variant_widths)
        widths.update({self.settings.export.medium_width, self.settings.export.small_width})
        return sorted(widths)

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
            contrast=adj.get("contrast", 1.0),
            saturation=adj.get("saturation", 1.0),
            temperature=adj.get("temperature", 0),
        )
        self._sync_temperature_slider(self.adjustment_state.temperature)

        current = payload.get("current_image")
        if current:
            self.current_adjusted_image = current.copy()
            self.canvas.display_pil_image(self.current_adjusted_image)
        else:
            self.current_adjusted_image = None
            self.canvas.clear()

        variants = payload.get("variants", {})
        self.latest_variants = {key: img.copy() for key, img in variants.items()}
        self.export_action.setEnabled(bool(self.latest_variants))

    def _has_unsaved_changes(self) -> bool:
        return bool(self.base_image or self.image_store.has_unsaved_changes())

    def export_variants(self) -> None:
        if not self.image_store.current or not self.latest_variants:
            self._show_error("Keine Varianten zum Export vorhanden.")
            return

        base_path = self.image_store.current.path

        try:
            paths = self.export_service.export_variants(base_path, self.latest_variants)
        except ExportServiceError as exc:
            self._show_error(str(exc))
            return

        names = ", ".join(path.name for path in paths)
        self.status_bar.showMessage(f"Exportiert: {names}", 7000)
