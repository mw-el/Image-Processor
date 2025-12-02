from __future__ import annotations

import logging
from fractions import Fraction
from pathlib import Path
from typing import Iterable, Any

from PySide6.QtCore import Qt, QRectF, QTimer, QSize
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QAction
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QAbstractItemView,
    QApplication,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSlider,
    QSizePolicy,
    QStatusBar,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
import qtawesome as qta

from PIL import Image

from ..core.adjustments import (
    AdjustmentState,
    apply_adjustments,
    calculate_auto_balance_photoshop_style,
    calculate_auto_balance_conservative,
    calculate_auto_balance_color_only,
)
from ..core.adjustment_controller import AdjustmentController
from ..core.image_session import ImageSession, ImageSessionError
from ..core.image_store import ImageStore, ImageState
from ..core.crop_service import compute_crop_box, perform_crop, CropServiceError
from ..core.image_processing import ProcessingPipeline, ProcessingError, ProcessingConfig
from ..core.export_service import ExportService, ExportServiceError, ExportConfig, ExportVariant
from ..core.settings import AppSettings
from ..core.crop_geometry import CropGeometry
from ..core.recent_manager import RecentManager
from .dialogs.custom_ratio_dialog import CustomRatioDialog
from .dialogs.results_viewer import ResultsViewerDialog
from .dialogs.save_as_dialog import SaveAsDialog
from .controllers.zoom_controller import ZoomController
from .views.image_canvas import ImageCanvas
from .components.file_browser_sidebar import FileBrowserSidebar
from .components.thumbnail_grid import ThumbnailGridView

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"}


class MainWindow(QMainWindow):
    """
    Basic application shell: menu, toolbar, drag & drop and placeholder canvas.
    Subsequent phases will replace the label with the actual image canvas.
    """

    def __init__(self, settings: AppSettings, initial_path: Path | None = None, initial_view: str = "single") -> None:
        super().__init__()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.image_store = ImageStore()
        self.settings = settings
        self._initial_path = initial_path
        self._initial_view = initial_view
        self.processing_pipeline = ProcessingPipeline(
            ProcessingConfig(
                sharpen_radius=settings.processing.sharpen_radius,
                sharpen_percent=settings.processing.sharpen_percent,
                sharpen_threshold=settings.processing.sharpen_threshold,
                resample_method=settings.processing.resample_method,
            ),
        )
        self.session = ImageSession(settings)
        self.adjustment_controller = AdjustmentController(self._on_adjustment_state_change)
        self.export_service = ExportService(
            ExportConfig(
                format=settings.export.format,
                quality=settings.export.quality,
                method=settings.export.method,
            )
        )
        self.has_ratio_selection = False
        self.active_ratio_button: QPushButton | None = None
        self.custom_ratio_tuple: tuple[float, float] | None = None
        self.custom_ratio_button: QPushButton | None = None
        self.current_image_path: Path | None = None
        self.current_folder: Path | None = None
        self.current_adjusted_image: Image.Image | None = None
        self.metadata_text = ""
        self.metadata_dirty = False
        self.loaded_metadata: dict[str, str] = {}
        self.current_resolution: tuple[int, int] = (0, 0)
        self.info_dialog: QDialog | None = None
        self.crop_geometry: CropGeometry | None = None
        self.last_exported_paths: list[Path] = []
        self.balance_mode: int = 0  # 0=none, 1=photoshop, 2=conservative, 3=color-only
        self.recent_manager = RecentManager()
        self.view_mode = "single"
        self._gallery_current_directory: Path | None = None
        self._gallery_image_count: int = 0

        self.setWindowTitle("AA Image Processor")
        self.resize(1580, 900)  # +300px for browser sidebar
        self.setAcceptDrops(True)

        self._create_actions()
        self._create_menus()
        self._create_ui_with_browser()

    # --- UI creation helpers -------------------------------------------------
    def _create_actions(self) -> None:
        self.open_action = QAction("Bild öffnen …", self)
        self.open_action.setShortcut("Ctrl+O")
        self.open_action.triggered.connect(self.open_image_dialog)

        self.save_action = QAction("Änderungen speichern", self)
        self.save_action.setShortcut("Ctrl+S")
        self.save_action.triggered.connect(self._save_simple)
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

        self.toggle_browser_action = QAction("Browser ein/aus", self)
        self.toggle_browser_action.setCheckable(True)
        self.toggle_browser_action.setChecked(True)  # Initial visible
        self.toggle_browser_action.triggered.connect(self._toggle_file_browser)

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

    def _create_ui_with_browser(self) -> None:
        """Create main UI with browser in right panel."""
        # Main container
        main_container = QWidget()
        main_layout = QVBoxLayout(main_container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Central content widget
        self._create_central_content(main_layout)

        # Statusbar
        self.status_bar = QStatusBar()
        main_layout.addWidget(self.status_bar)

        # Set as central widget
        self.setCentralWidget(main_container)

        self._set_adjustment_controls_enabled(False)
        self._update_history_actions()
        if self._initial_path:
            QTimer.singleShot(0, lambda: self._open_initial_image(self._initial_path))

    def _create_central_content(self, parent_layout: QVBoxLayout) -> None:
        """Create the main content area (canvas + controls)."""
        content_widget = QWidget()
        root_layout = QHBoxLayout(content_widget)
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.setSpacing(12)

        # Common button styles - icons always white
        self.btn_style_normal = """
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
            QPushButton:disabled {
                background-color: #9E9E9E;
                color: white;
            }
        """

        self.btn_style_checkable = """
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
            QPushButton:checked {
                background-color: #FF7043;
            }
            QPushButton:checked:hover {
                background-color: #F4511E;
            }
            QPushButton:disabled {
                background-color: #9E9E9E;
                color: white;
            }
        """

        self.canvas = ImageCanvas()
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.canvas.navigate_previous.connect(self._navigate_to_previous_image)
        self.canvas.navigate_next.connect(self._navigate_to_next_image)
        self.canvas.crop_overlay.crop_requested.connect(self.apply_crop)

        single_view_container = QWidget()
        single_view_layout = QVBoxLayout(single_view_container)
        single_view_layout.setContentsMargins(0, 0, 0, 0)
        single_view_layout.setSpacing(6)
        single_view_layout.addWidget(self.canvas, stretch=1)

        zoom_layout = QHBoxLayout()
        zoom_layout.setContentsMargins(0, 0, 0, 0)
        zoom_layout.setSpacing(6)
        self.zoom_label = QLabel("Zoom: 100%")
        self.zoom_slider = QSlider(Qt.Horizontal)
        self.zoom_slider.setRange(10, 200)
        self.zoom_slider.setValue(100)
        zoom_layout.addWidget(self.zoom_label)
        zoom_layout.addWidget(self.zoom_slider, stretch=1)
        single_view_layout.addLayout(zoom_layout)

        # === Gallery view ===
        self.gallery_grid = ThumbnailGridView()
        self.gallery_grid.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.gallery_grid.itemSelectionChanged.connect(self._update_gallery_selection_state)
        self.gallery_grid.itemDoubleClicked.connect(self._open_image_from_gallery_item)

        gallery_toolbar = QHBoxLayout()
        gallery_toolbar.setContentsMargins(0, 0, 0, 0)
        gallery_toolbar.setSpacing(8)
        self.gallery_title_label = QLabel("Galerieansicht")
        self.gallery_title_label.setStyleSheet("font-weight: bold;")
        gallery_toolbar.addWidget(self.gallery_title_label)
        gallery_toolbar.addStretch()
        self.gallery_selection_label = QLabel("")
        gallery_toolbar.addWidget(self.gallery_selection_label)
        self.delete_selected_btn = QPushButton()
        self.delete_selected_btn.setIcon(qta.icon("mdi6.delete", color="white"))
        self.delete_selected_btn.setIconSize(QSize(20, 20))
        self.delete_selected_btn.setFixedHeight(32)
        self.delete_selected_btn.setFixedWidth(32)
        self.delete_selected_btn.setStyleSheet(self.btn_style_normal)
        self.delete_selected_btn.setEnabled(False)
        self.delete_selected_btn.setToolTip("Ausgewählte Bilder löschen")
        self.delete_selected_btn.clicked.connect(self._delete_selected_images)
        gallery_toolbar.addWidget(self.delete_selected_btn)

        gallery_container = QWidget()
        gallery_layout = QVBoxLayout(gallery_container)
        gallery_layout.setContentsMargins(0, 0, 0, 0)
        gallery_layout.setSpacing(6)
        gallery_layout.addLayout(gallery_toolbar)
        gallery_layout.addWidget(self.gallery_grid, stretch=1)

        # Stack for switching between single view and gallery
        self.viewer_stack = QStackedWidget()
        self.viewer_stack.addWidget(single_view_container)  # index 0
        self.viewer_stack.addWidget(gallery_container)     # index 1
        self.viewer_stack.setCurrentIndex(0)

        root_layout.addWidget(self.viewer_stack, stretch=3)
        self.zoom_controller = ZoomController(self.canvas, self.zoom_slider, self.zoom_label)
        self.zoom_controller.set_enabled(False)

        self.controls_width = 360
        controls_widget = QWidget()
        controls_widget.setFixedWidth(self.controls_width)
        controls_layout = QVBoxLayout(controls_widget)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(6)

        self.adjustment_controls: list[QWidget] = []
        btn_size = 40  # Square button size for icon buttons

        # === ROW 1: File operation buttons (top) - always visible ===
        file_row = QHBoxLayout()
        file_row.setSpacing(6)

        # Open file (system dialog)
        self.open_file_btn = QPushButton()
        self.open_file_btn.setIcon(qta.icon("mdi6.folder-open", color="white"))
        self.open_file_btn.setIconSize(QSize(24, 24))
        self.open_file_btn.setToolTip("Bild öffnen (Systemdialog)")
        self.open_file_btn.setFixedSize(btn_size, btn_size)
        self.open_file_btn.setStyleSheet(self.btn_style_normal)
        self.open_file_btn.clicked.connect(self.open_image_dialog)
        file_row.addWidget(self.open_file_btn)

        # Recent images button with dropdown
        self.recent_images_btn = QPushButton()
        self.recent_images_btn.setIcon(qta.icon("mdi6.image-multiple", color="white"))
        self.recent_images_btn.setIconSize(QSize(24, 24))
        self.recent_images_btn.setToolTip("Zuletzt geöffnete Bilder")
        self.recent_images_btn.setFixedSize(btn_size, btn_size)
        self.recent_images_btn.setStyleSheet(self.btn_style_normal)
        self.recent_images_btn.clicked.connect(self._show_recent_images_menu)
        file_row.addWidget(self.recent_images_btn)

        # Recent folders button with dropdown
        self.recent_folders_btn = QPushButton()
        self.recent_folders_btn.setIcon(qta.icon("mdi6.folder-clock", color="white"))
        self.recent_folders_btn.setIconSize(QSize(24, 24))
        self.recent_folders_btn.setToolTip("Zuletzt geöffnete Ordner")
        self.recent_folders_btn.setFixedSize(btn_size, btn_size)
        self.recent_folders_btn.setStyleSheet(self.btn_style_normal)
        self.recent_folders_btn.clicked.connect(self._show_recent_folders_menu)
        file_row.addWidget(self.recent_folders_btn)

        # Toggle browser panel
        self.toggle_browser_btn = QPushButton()
        self.toggle_browser_btn.setIcon(qta.icon("mdi6.folder-eye", color="white"))
        self.toggle_browser_btn.setIconSize(QSize(24, 24))
        self.toggle_browser_btn.setToolTip("Browser-Panel ein/aus")
        self.toggle_browser_btn.setFixedSize(btn_size, btn_size)
        self.toggle_browser_btn.setCheckable(True)
        self.toggle_browser_btn.setChecked(False)  # Start hidden
        self.toggle_browser_btn.setStyleSheet(self.btn_style_checkable)
        self.toggle_browser_btn.clicked.connect(self._toggle_file_browser)
        file_row.addWidget(self.toggle_browser_btn)

        # Undo
        self.undo_btn = QPushButton()
        self.undo_btn.setIcon(qta.icon("mdi6.undo", color="white"))
        self.undo_btn.setIconSize(QSize(24, 24))
        self.undo_btn.setToolTip("Rückgängig (Ctrl+Z)")
        self.undo_btn.setFixedSize(btn_size, btn_size)
        self.undo_btn.setStyleSheet(self.btn_style_normal)
        self.undo_btn.clicked.connect(self.undo_change)
        self.undo_btn.setEnabled(False)
        file_row.addWidget(self.undo_btn)

        # Redo
        self.redo_btn = QPushButton()
        self.redo_btn.setIcon(qta.icon("mdi6.redo", color="white"))
        self.redo_btn.setIconSize(QSize(24, 24))
        self.redo_btn.setToolTip("Wiederholen (Ctrl+Shift+Z)")
        self.redo_btn.setFixedSize(btn_size, btn_size)
        self.redo_btn.setStyleSheet(self.btn_style_normal)
        self.redo_btn.clicked.connect(self.redo_change)
        self.redo_btn.setEnabled(False)
        file_row.addWidget(self.redo_btn)

        # Reset to original
        self.reset_original_btn = QPushButton()
        self.reset_original_btn.setIcon(qta.icon("mdi6.image-refresh", color="white"))
        self.reset_original_btn.setIconSize(QSize(24, 24))
        self.reset_original_btn.setToolTip("Zurück zum Original (Ctrl+R)")
        self.reset_original_btn.setFixedSize(btn_size, btn_size)
        self.reset_original_btn.setStyleSheet(self.btn_style_normal)
        self.reset_original_btn.clicked.connect(self.reset_to_original)
        self.reset_original_btn.setEnabled(False)
        file_row.addWidget(self.reset_original_btn)

        file_row.addStretch()
        controls_layout.addLayout(file_row)

        # === File browser (shows when toggle is checked) ===
        self.file_browser = FileBrowserSidebar(start_path=Path.home())
        self.file_browser.image_selected.connect(self._handle_file_drop)
        self.file_browser.hide()  # Start hidden
        controls_layout.addWidget(self.file_browser, stretch=1)

        # === Image controls container (shows when browser is hidden AND image loaded) ===
        self.image_controls_container = QWidget()
        image_controls_layout = QVBoxLayout(self.image_controls_container)
        image_controls_layout.setContentsMargins(0, 0, 0, 0)
        image_controls_layout.setSpacing(6)

        # === Aspect Ratio buttons ===
        ratio_grid = QGridLayout()
        ratio_grid.setSpacing(6)
        self.ratio_buttons: dict[str, QPushButton] = {}
        ratio_button_width = int(self.controls_width / 5) - 4

        # View toggle buttons (left column)
        self.single_view_btn = QPushButton()
        self.single_view_btn.setIcon(qta.icon("mdi6.image-outline", color="white"))
        self.single_view_btn.setIconSize(QSize(20, 20))
        self.single_view_btn.setToolTip("Einzelansicht")
        self.single_view_btn.setCheckable(True)
        self.single_view_btn.setChecked(True)
        self.single_view_btn.setFixedWidth(ratio_button_width)
        self.single_view_btn.setFixedHeight(32)
        self.single_view_btn.setStyleSheet(self.btn_style_checkable)
        self.single_view_btn.clicked.connect(lambda: self._set_view_mode("single"))
        ratio_grid.addWidget(self.single_view_btn, 0, 0)

        self.gallery_view_btn = QPushButton()
        self.gallery_view_btn.setIcon(qta.icon("mdi6.view-grid-outline", color="white"))
        self.gallery_view_btn.setIconSize(QSize(20, 20))
        self.gallery_view_btn.setToolTip("Galerieansicht")
        self.gallery_view_btn.setCheckable(True)
        self.gallery_view_btn.setChecked(False)
        self.gallery_view_btn.setFixedWidth(ratio_button_width)
        self.gallery_view_btn.setFixedHeight(32)
        self.gallery_view_btn.setStyleSheet(self.btn_style_checkable)
        self.gallery_view_btn.clicked.connect(lambda: self._set_view_mode("gallery"))
        ratio_grid.addWidget(self.gallery_view_btn, 1, 0)

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
            btn.setFixedWidth(ratio_button_width)
            btn.setFixedHeight(32)
            btn.setStyleSheet(self.btn_style_checkable)
            btn.clicked.connect(lambda checked, b=btn, lbl=label, r=ratio: self._ratio_button_clicked(b, lbl, r))
            row = idx // 4
            col = (idx % 4) + 1
            ratio_grid.addWidget(btn, row, col)
            self.ratio_buttons[label] = btn
            if label == "?:?":
                self.custom_ratio_button = btn

        image_controls_layout.addLayout(ratio_grid)

        # === Accordion header (Auto + Reset + Expand) ===
        accordion_header = QHBoxLayout()
        accordion_header.setSpacing(6)

        self.auto_balance_btn = QPushButton()
        self.auto_balance_btn.setIcon(qta.icon("fa5s.magic", color="white"))
        self.auto_balance_btn.setIconSize(QSize(24, 24))
        self.auto_balance_btn.setToolTip("Automatische Anpassungen durchprobieren")
        self.auto_balance_btn.clicked.connect(self._auto_color_balance)
        self.auto_balance_btn.setFixedSize(btn_size, btn_size)
        self.auto_balance_btn.setStyleSheet(self.btn_style_normal)
        accordion_header.addWidget(self.auto_balance_btn)
        self.adjustment_controls.append(self.auto_balance_btn)

        self.reset_sliders_btn = QPushButton()
        self.reset_sliders_btn.setIcon(qta.icon("mdi6.refresh", color="white"))
        self.reset_sliders_btn.setIconSize(QSize(24, 24))
        self.reset_sliders_btn.setToolTip("Alle Regler auf Standardwerte zurücksetzen")
        self.reset_sliders_btn.clicked.connect(self._reset_sliders_clicked)
        self.reset_sliders_btn.setFixedSize(btn_size, btn_size)
        self.reset_sliders_btn.setStyleSheet(self.btn_style_normal)
        accordion_header.addWidget(self.reset_sliders_btn)
        self.adjustment_controls.append(self.reset_sliders_btn)

        accordion_header.addStretch()

        # Expand/collapse button for sliders
        self.expand_sliders_btn = QPushButton()
        self.expand_sliders_btn.setIcon(qta.icon("mdi6.chevron-down", color="white"))
        self.expand_sliders_btn.setIconSize(QSize(24, 24))
        self.expand_sliders_btn.setToolTip("Feineinstellungen ein-/ausblenden")
        self.expand_sliders_btn.setFixedSize(btn_size, btn_size)
        self.expand_sliders_btn.setCheckable(True)
        self.expand_sliders_btn.setStyleSheet(self.btn_style_checkable)
        self.expand_sliders_btn.clicked.connect(self._toggle_sliders_visibility)
        accordion_header.addWidget(self.expand_sliders_btn)

        image_controls_layout.addLayout(accordion_header)

        # === Slider container (collapsible) ===
        self.sliders_container = QWidget()
        sliders_layout = QVBoxLayout(self.sliders_container)
        sliders_layout.setContentsMargins(0, 0, 0, 0)
        sliders_layout.setSpacing(4)
        self.factor_sliders: dict[str, dict[str, Any]] = {}

        factor_slider_defs = [
            ("brightness", "Helligkeit", "mdi6.brightness-6"),
            ("contrast", "Kontrast", "mdi6.contrast-box"),
            ("saturation", "Sättigung", "mdi6.palette"),
            ("sharpness", "Schärfe", "mdi6.blur"),
        ]
        for field, title, icon_name in factor_slider_defs:
            slider, label = self._add_factor_slider_with_icon(sliders_layout, field, title, icon_name)
            self.factor_sliders[field] = {"slider": slider, "label": label, "title": title}

        # Temperature slider
        temp_row = QHBoxLayout()
        temp_icon = QLabel()
        temp_icon.setPixmap(qta.icon("mdi6.thermometer", color="#666").pixmap(20, 20))
        temp_icon.setFixedWidth(24)
        temp_row.addWidget(temp_icon)
        self.temperature_label = QLabel("0")
        self.temperature_label.setFixedWidth(30)
        temp_row.addWidget(self.temperature_label)
        self.temperature_slider = QSlider(Qt.Horizontal)
        self.temperature_slider.setRange(-100, 100)
        self.temperature_slider.setValue(0)
        self.temperature_slider.valueChanged.connect(self._temperature_changed)
        self.temperature_slider.sliderReleased.connect(self._commit_temperature_state)
        temp_row.addWidget(self.temperature_slider)
        sliders_layout.addLayout(temp_row)
        self.adjustment_controls.extend([self.temperature_label, self.temperature_slider])

        # RGB Balance Sliders
        for color, label_attr, slider_attr, change_method, color_hex in [
            ("Rot", "red_balance_label", "red_balance_slider", self._red_balance_changed, "#F44336"),
            ("Grün", "green_balance_label", "green_balance_slider", self._green_balance_changed, "#4CAF50"),
            ("Blau", "blue_balance_label", "blue_balance_slider", self._blue_balance_changed, "#2196F3"),
        ]:
            row = QHBoxLayout()
            icon = QLabel()
            icon.setPixmap(qta.icon("mdi6.circle", color=color_hex).pixmap(20, 20))
            icon.setFixedWidth(24)
            row.addWidget(icon)
            label = QLabel("0")
            label.setFixedWidth(30)
            setattr(self, label_attr, label)
            row.addWidget(label)
            slider = QSlider(Qt.Horizontal)
            slider.setRange(-100, 100)
            slider.setValue(0)
            slider.valueChanged.connect(change_method)
            slider.sliderReleased.connect(lambda c=color: self._commit_rgb_state(f"{c}-Balance"))
            setattr(self, slider_attr, slider)
            row.addWidget(slider)
            sliders_layout.addLayout(row)
            self.adjustment_controls.extend([label, slider])

        # Hide sliders by default
        self.sliders_container.hide()
        image_controls_layout.addWidget(self.sliders_container)

        # Stretch to push save buttons to bottom
        image_controls_layout.addStretch()

        # === Status log ===
        # === Filename display ===
        self.filename_label = QLabel("-")
        self.filename_label.setStyleSheet("font-weight: bold;")
        image_controls_layout.addWidget(self.filename_label)

        # === Save buttons ===
        save_row = QHBoxLayout()
        save_row.setSpacing(6)

        # Simple save: overwrite original with current adjustments
        self.save_simple_btn = QPushButton()
        self.save_simple_btn.setIcon(qta.icon("mdi6.content-save", color="white"))
        self.save_simple_btn.setIconSize(QSize(24, 24))
        self.save_simple_btn.setToolTip("Bild mit Änderungen speichern (überschreibt Original)")
        self.save_simple_btn.setFixedSize(btn_size, btn_size)
        self.save_simple_btn.setStyleSheet(self.btn_style_normal)
        self.save_simple_btn.clicked.connect(self._save_simple)
        save_row.addWidget(self.save_simple_btn)
        self.adjustment_controls.append(self.save_simple_btn)

        # Export variants: multiple resolutions
        self.save_changes_btn = QPushButton()
        self.save_changes_btn.setIcon(qta.icon("mdi6.content-save-all", color="white"))
        self.save_changes_btn.setIconSize(QSize(24, 24))
        self.save_changes_btn.setToolTip("Varianten speichern (mehrere Auflösungen)")
        self.save_changes_btn.setFixedSize(btn_size, btn_size)
        self.save_changes_btn.setStyleSheet(self.btn_style_normal)
        self.save_changes_btn.clicked.connect(self.export_variants)
        save_row.addWidget(self.save_changes_btn)
        self.adjustment_controls.append(self.save_changes_btn)

        self.save_as_btn = QPushButton()
        self.save_as_btn.setIcon(qta.icon("mdi6.content-save-cog", color="white"))
        self.save_as_btn.setIconSize(QSize(24, 24))
        self.save_as_btn.setToolTip("Mit Auflösung und Format speichern")
        self.save_as_btn.setFixedSize(btn_size, btn_size)
        self.save_as_btn.setStyleSheet(self.btn_style_normal)
        self.save_as_btn.clicked.connect(self._save_variants_as)
        save_row.addWidget(self.save_as_btn)
        self.adjustment_controls.append(self.save_as_btn)

        self.view_results_btn = QPushButton()
        self.view_results_btn.setIcon(qta.icon("mdi6.eye", color="white"))
        self.view_results_btn.setIconSize(QSize(24, 24))
        self.view_results_btn.setToolTip("Exportierte Bilder im Vergleich mit Original anzeigen")
        self.view_results_btn.setEnabled(False)
        self.view_results_btn.setFixedSize(btn_size, btn_size)
        self.view_results_btn.setStyleSheet(self.btn_style_normal)
        self.view_results_btn.clicked.connect(self._show_results_viewer)
        save_row.addWidget(self.view_results_btn)

        # Open in ComfyUI (single view)
        self.open_in_comfy_btn = QPushButton()
        self.open_in_comfy_btn.setIcon(qta.icon("mdi6.puzzle", color="white"))
        self.open_in_comfy_btn.setIconSize(QSize(22, 22))
        self.open_in_comfy_btn.setToolTip("In ComfyUI laden")
        self.open_in_comfy_btn.setFixedSize(btn_size, btn_size)
        self.open_in_comfy_btn.setStyleSheet(self.btn_style_normal)
        self.open_in_comfy_btn.clicked.connect(lambda: self._open_in_comfyui(self.current_image_path))
        self.open_in_comfy_btn.setEnabled(False)
        save_row.addWidget(self.open_in_comfy_btn)

        self.info_btn = QPushButton()
        self.info_btn.setIcon(qta.icon("mdi6.information", color="white"))
        self.info_btn.setIconSize(QSize(24, 24))
        self.info_btn.setToolTip("Datei- und Metadaten anzeigen")
        self.info_btn.setFixedSize(btn_size, btn_size)
        self.info_btn.setStyleSheet(self.btn_style_normal)
        self.info_btn.clicked.connect(self._show_image_info_dialog)
        save_row.addWidget(self.info_btn)
        self.adjustment_controls.append(self.info_btn)

        save_row.addStretch()
        image_controls_layout.addLayout(save_row)

        controls_layout.addWidget(self.image_controls_container, stretch=1)

        # Add stretch at end to push file_row to top when containers are hidden
        controls_layout.addStretch()

        root_layout.addWidget(controls_widget, stretch=1)

        # Add content widget to parent layout
        parent_layout.addWidget(content_widget)

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
        self._reset_zoom_controls()
        self.current_image_path = path
        try:
            image = self.session.load(path)
        except ImageSessionError as exc:
            self._show_error(str(exc))
            return
        self.current_folder = path.parent
        self.current_adjusted_image = image.copy()
        self.canvas.display_pil_image(image)
        self.zoom_controller.reset()
        self.zoom_controller.set_enabled(True)
        self.adjustment_controller.reset()
        self._sync_all_sliders()
        self.metadata_dirty = False
        self._set_adjustment_controls_enabled(True)
        self._enable_save_buttons(True)
        self._update_history_actions()
        self._update_comfy_button_state()
        self.logger.info("Bild geladen: %s", path)
        self.status_bar.showMessage(f"Aktuelles Bild: {path.name}", 5000)
        self._append_status(f"Geladen: {path}")
        self._load_metadata_info(path)
        # Add to recent files and folders
        self.recent_manager.add_file(path)
        self.recent_manager.add_folder(path.parent)
        self._update_navigation_buttons()
        self._set_view_mode("single")
        self._refresh_gallery_from_current_image(load=True)

        # Hide browser and show image controls after loading image
        self.toggle_browser_btn.setChecked(False)
        if hasattr(self, "toggle_browser_action"):
            self.toggle_browser_action.setChecked(False)
        self._toggle_file_browser(False)

    def _open_initial_image(self, path: Path) -> None:
        if not path.exists():
            self.status_bar.showMessage(f"Datei nicht gefunden: {path}", 7000)
            return
        self._handle_file_drop(path)
        # If initial view is gallery, switch after loading the image
        if self._initial_view == "gallery":
            QTimer.singleShot(100, lambda: self._set_view_mode("gallery"))

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

    def _resolve_model_path(self, configured_path: str) -> Path:
        path = Path(configured_path).expanduser()
        if not path.is_absolute():
            root = Path(__file__).resolve().parents[2]
            path = root / path
        return path

    def _show_error(self, message: str) -> None:
        QMessageBox.critical(self, "Fehler", message)
        self.status_bar.showMessage(message, 5000)

    # --- Ratio handling ------------------------------------------------------
    def _apply_ratio(self, ratio: float, target_width: float | None = None, target_height: float | None = None) -> bool:
        self._append_status(f"_apply_ratio aufgerufen mit ratio={ratio:.4f}, target_size={target_width}x{target_height if target_width else 'auto'}")
        if not self.session.has_image():
            self._show_error("Bitte zuerst ein Bild laden.")
            self._append_status("✗ Fehler: Kein Bild in Session")
            return False
        pixmap = self.canvas.current_pixmap()
        if pixmap is None or pixmap.isNull():
            self._show_error("Kein Bild geladen.")
            self._append_status("✗ Fehler: Canvas Pixmap ist None oder null")
            return False
        rect = self.canvas.image_rect_in_canvas()
        self._append_status(f"Canvas Bildbereich: {rect.width():.1f}x{rect.height():.1f}")
        if rect.width() <= 0 or rect.height() <= 0:
            rect = QRectF(self.canvas.rect())
        if rect.width() <= 0 or rect.height() <= 0:
            self._show_error("Bildbereich konnte nicht berechnet werden.")
            self._append_status("✗ Fehler: Ungültiger Bildbereich")
            return False

        # Compute centered rect - use explicit dimensions for custom ratios
        if target_width is not None and target_height is not None:
            # Custom ratio: scale user's dimensions to fit in canvas
            scale = min(rect.width() / target_width, rect.height() / target_height, 1.0)
            width = max(1, target_width * scale)
            height = max(1, target_height * scale)
            x = rect.center().x() - width / 2
            y = rect.center().y() - height / 2
            centered_rect = QRectF(x, y, width, height)
            self._append_status(f"Custom Ratio: Skaliere {target_width}x{target_height} mit Faktor {scale:.3f}")
        else:
            # Preset ratio: use existing logic
            centered_rect = self._compute_centered_rect(rect, ratio)

        self._append_status(f"Crop-Bereich berechnet: {centered_rect.width():.1f}x{centered_rect.height():.1f}")
        self.canvas.crop_overlay.set_selection(centered_rect, ratio)
        self.has_ratio_selection = True
        self.logger.info("Aspect Ratio gesetzt: %.4f", ratio)
        self._append_status(f"✓ Crop-Overlay aktiviert mit Ratio {ratio:.4f}")
        return True

    def _compute_centered_rect(self, bounds, ratio: float):
        width = bounds.width()
        height = width / ratio
        if height > bounds.height():
            height = bounds.height()
            width = height * ratio
        x = bounds.center().x() - width / 2
        y = bounds.center().y() - height / 2
        return QRectF(x, y, width, height)

    def _rect_to_tuple(self, rect: QRectF) -> tuple[float, float, float, float]:
        return (rect.x(), rect.y(), rect.width(), rect.height())

    def _store_crop_geometry(self, selection_rect: QRectF, image_rect: QRectF, scale: float) -> None:
        if image_rect.width() <= 0 or image_rect.height() <= 0:
            self.crop_geometry = None
            return
        scale = max(scale, 1e-6)
        self.crop_geometry = CropGeometry(
            selection=self._rect_to_tuple(selection_rect),
            image_bounds=self._rect_to_tuple(image_rect),
            scale=scale,
        )


    def _ratio_button_clicked(self, button: QPushButton, label: str, ratio: float | None) -> None:
        if button is self.active_ratio_button:
            button.setChecked(False)
            self.active_ratio_button = None
            self.canvas.crop_overlay.clear_selection()
            self.has_ratio_selection = False
            self.session.clear_ratio()
            self.crop_geometry = None
            self.status_bar.showMessage("Aspect Ratio entfernt", 4000)
            return

        if not self.session.has_image():
            self._show_error("Bitte zuerst ein Bild laden.")
            button.setChecked(False)
            self.active_ratio_button = None
            return

        if self.active_ratio_button:
            self.active_ratio_button.setChecked(False)
        self.active_ratio_button = button
        self._enter_crop_mode()
        modifiers = QApplication.keyboardModifiers()
        ratio_value: float | None = None
        label_text = label
        custom_tuple: tuple[float, float] | None = None

        if ratio is None:
            use_stored = self.custom_ratio_tuple and not (modifiers & Qt.ShiftModifier)
            if use_stored and self.custom_ratio_tuple:
                width, height = self.custom_ratio_tuple
                ratio_value = width / height if height else 1.0
                label_text = f"{int(width)}:{int(height)}"
                custom_tuple = self.custom_ratio_tuple
            else:
                # Pass last custom ratio as default values
                default_w = self.custom_ratio_tuple[0] if self.custom_ratio_tuple else 0
                default_h = self.custom_ratio_tuple[1] if self.custom_ratio_tuple else 0
                self._append_status(f"Öffne Custom Ratio Dialog (Standard: {default_w}:{default_h})")
                dialog = CustomRatioDialog(self, default_width=default_w, default_height=default_h)
                if dialog.exec() == dialog.Accepted and dialog.selection:
                    width = dialog.selection.width
                    height = dialog.selection.height
                    self.custom_ratio_tuple = (width, height)
                    ratio_value = width / height if height else 1.0
                    label_text = f"{int(width)}:{int(height)}"
                    custom_tuple = self.custom_ratio_tuple
                    self._append_status(f"Custom Ratio gewählt: {label_text} = {ratio_value:.4f}")
                    if self.custom_ratio_button:
                        self.custom_ratio_button.setText(label_text)
                else:
                    self._append_status("Custom Ratio Dialog abgebrochen")
                    button.setChecked(False)
                    self.active_ratio_button = None
                    return
        else:
            ratio_value = ratio

        if ratio_value is None or ratio_value <= 0:
            self._show_error("Ungültiges Aspect Ratio.")
            button.setChecked(False)
            self.active_ratio_button = None
            return

        self.session.set_ratio(label_text, ratio_value, custom_tuple)
        # For custom ratios, pass explicit dimensions; for preset ratios, pass None
        target_w = custom_tuple[0] if custom_tuple else None
        target_h = custom_tuple[1] if custom_tuple else None
        if not self._apply_ratio(ratio_value, target_width=target_w, target_height=target_h):
            self.session.clear_ratio()
            button.setChecked(False)
            self.active_ratio_button = None
            self.has_ratio_selection = False
            self._exit_crop_mode()
            return

        button.setChecked(True)
        self.has_ratio_selection = True
        self.status_bar.showMessage(f"Aspect Ratio gesetzt: {label_text}", 4000)

    def _enter_crop_mode(self) -> None:
        if not self.session.has_image():
            return
        self.session.reset_base_to_original()
        self.current_adjusted_image = None
        self.crop_geometry = None
        # Display the base image on canvas
        base_image = self.session.current_base()
        self.canvas.display_pil_image(base_image)
        self._append_status("Crop-Modus aktiviert")

    def _exit_crop_mode(self) -> None:
        """Exit crop mode without applying crop."""
        self.canvas.crop_overlay.clear_selection()
        self._append_status("Crop-Modus verlassen")

    def apply_crop(self) -> None:
        selection = self.canvas.crop_overlay.current_selection()
        pixmap = self.canvas.current_pixmap()
        if not self.image_store.current or not selection or pixmap is None:
            self._show_error("Bitte Bild laden und Aspect Ratio auswählen.")
            return
        if not self.has_ratio_selection:
            self._show_error("Bitte zuerst ein Aspect Ratio auswählen.")
            return

        image_rect = self.canvas.image_rect_in_canvas()
        scale = self.canvas.current_scale()

        try:
            crop_box = compute_crop_box(selection.rect, image_rect, pixmap, scale)
            cropped_image = perform_crop(pixmap, crop_box)
        except CropServiceError as exc:
            self._show_error(str(exc))
            return

        self._store_crop_geometry(selection.rect, image_rect, scale)
        self.session.set_base_image(cropped_image)
        self.adjustment_controller.reset()
        self._sync_all_sliders()
        self._set_adjustment_controls_enabled(True)
        self._render_adjusted_image()
        self._enable_save_buttons(True)
        self._commit_current_state(f"Crop {selection.aspect_ratio:.2f}")
        self.status_bar.showMessage("Ausschnitt angewendet", 5000)
        applied_label = self.session.ratio.label or "n/a"
        self._append_status(f"Ausschnitt angewendet ({applied_label})")

    # --- Adjustments --------------------------------------------------------
    def _render_adjusted_image(self) -> None:
        if not self.session.has_image():
            return
        try:
            adjusted = self.session.apply_adjustments(self.adjustment_controller.state)
        except ImageSessionError as exc:
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
        snapshot = self._snapshot_adjustment_state()
        self.image_store.push_state(
            ImageState(
                path=self.image_store.current.path,
                description=description,
                payload={
                    "base_image": self.session.current_base() if self.session.has_image() else None,
                    "adjustment_state": {
                        "brightness": snapshot.brightness,
                        "contrast": snapshot.contrast,
                        "saturation": snapshot.saturation,
                        "sharpness": snapshot.sharpness,
                        "temperature": snapshot.temperature,
                    },
                    "current_image": image.copy(),
                    "metadata_text": self.metadata_text,
                    "crop_geometry": self.crop_geometry.to_payload() if self.crop_geometry else None,
                },
            )
        )
        self._update_history_actions()

    def _on_adjustment_state_change(self, state: AdjustmentState) -> None:
        if not self.session.has_image():
            return
        try:
            adjusted = self.session.apply_adjustments(state)
        except ImageSessionError as exc:
            self._show_error(str(exc))
            return
        self.current_adjusted_image = adjusted
        self.canvas.display_pil_image(adjusted)
        self._enable_save_buttons(True)

    def _on_factor_slider_change(self, field: str, title: str, value: int, label: QLabel) -> None:
        factor = self._slider_to_factor(value)
        label.setText(f"{factor:.2f}")
        self.adjustment_controller.update_factor(field, factor)

    def _commit_factor_state(self, title: str) -> None:
        if not self.session.has_image():
            return
        self._commit_current_state(f"{title} angepasst")

    def _temperature_changed(self, value: int) -> None:
        self.temperature_label.setText(str(value))
        self.adjustment_controller.update_temperature(value)

    def _commit_temperature_state(self) -> None:
        if not self.session.has_image():
            return
        self._commit_current_state("Temperatur angepasst")

    def _red_balance_changed(self, value: int) -> None:
        self.red_balance_label.setText(str(value))
        self.adjustment_controller.update_red_balance(value)

    def _green_balance_changed(self, value: int) -> None:
        self.green_balance_label.setText(str(value))
        self.adjustment_controller.update_green_balance(value)

    def _blue_balance_changed(self, value: int) -> None:
        self.blue_balance_label.setText(str(value))
        self.adjustment_controller.update_blue_balance(value)

    def _commit_rgb_state(self, label: str) -> None:
        if not self.session.has_image():
            return
        self._commit_current_state(f"{label} angepasst")

    def _auto_color_balance(self) -> None:
        if not self.session.has_image():
            self._show_error("Bitte zuerst ein Bild laden.")
            return

        # Cycle through balance modes: 0 -> 1 -> 2 -> 3 -> 0
        self.balance_mode = (self.balance_mode % 3) + 1

        base_image = self.session.current_base()

        if self.balance_mode == 1:
            # Photoshop-style
            optimal_state = calculate_auto_balance_photoshop_style(base_image)
            mode_name = "Auto 1"
            self.auto_balance_btn.setIcon(qta.icon("fa5s.magic", color="white"))
            self.auto_balance_btn.setText(" Auto 1")
        elif self.balance_mode == 2:
            # Conservative
            optimal_state = calculate_auto_balance_conservative(base_image)
            mode_name = "Auto 2"
            self.auto_balance_btn.setIcon(qta.icon("fa5s.magic", color="white"))
            self.auto_balance_btn.setText(" Auto 2")
        else:  # mode == 3
            # Color-only
            optimal_state = calculate_auto_balance_color_only(base_image)
            mode_name = "Auto 3"
            self.auto_balance_btn.setIcon(qta.icon("fa5s.magic", color="white"))
            self.auto_balance_btn.setText(" Auto 3")

        self.adjustment_controller.set_state(optimal_state)
        self._sync_all_sliders()
        self._render_adjusted_image()
        self._commit_current_state(f"Auto-Balance: {mode_name}")
        self._append_status(f"Balance-Modus: {mode_name}")

    def _reset_adjustments(self) -> None:
        self.adjustment_controller.reset()
        self._sync_all_sliders()

    def _reset_sliders_clicked(self) -> None:
        if not self.session.has_image():
            self._show_error("Bitte zuerst einen Ausschnitt erzeugen.")
            return
        self.adjustment_controller.reset()
        self._sync_all_sliders()
        self._render_adjusted_image()
        self._commit_current_state("Einstellungen zurückgesetzt")
        self.balance_mode = 0
        self.auto_balance_btn.setIcon(qta.icon("fa5s.magic", color="white"))
        self.auto_balance_btn.setText("")

    def _show_results_viewer(self) -> None:
        """Open dialog to view original and exported images."""
        if not self.last_exported_paths or not self.current_image_path:
            self._show_error("Keine Ergebnisse zum Anzeigen vorhanden.")
            return

        try:
            dialog = ResultsViewerDialog(self.current_image_path, self.last_exported_paths, self)
            dialog.exec()
        except Exception as exc:
            self._show_error(f"Fehler beim Öffnen der Ergebnisansicht: {exc}")

    def _open_in_comfyui(self, image_path: Path | None) -> None:
        """Launch external ComfyUI GUI with current image preloaded."""
        if not image_path or not image_path.exists():
            self._show_error("Bitte zuerst ein Bild laden.")
            return
        if not self._comfy_script.exists():
            self._show_error(f"ComfyUI Startskript fehlt:\n{self._comfy_script}")
            return
        try:
            subprocess.Popen([str(self._comfy_script), "--load-image", str(image_path)])
            self._append_status(f"ComfyUI gestartet mit {image_path.name}")
        except Exception as exc:
            self._show_error(f"ComfyUI konnte nicht gestartet werden: {exc}")

    def _toggle_file_browser(self, checked: bool) -> None:
        """Toggle between file browser and image controls."""
        self.file_browser.setVisible(checked)
        if checked:
            self.image_controls_container.hide()
        else:
            self.file_browser.hide()
            self.image_controls_container.show()

    def _toggle_sliders_visibility(self, checked: bool) -> None:
        """Toggle slider container visibility (accordion)."""
        self.sliders_container.setVisible(checked)
        if checked:
            self.expand_sliders_btn.setIcon(qta.icon("mdi6.chevron-up", color="white"))
        else:
            self.expand_sliders_btn.setIcon(qta.icon("mdi6.chevron-down", color="white"))

    # --- View mode + Gallery -------------------------------------------------
    def _set_view_mode(self, mode: str) -> None:
        """Switch between single image view and gallery view."""
        if mode not in {"single", "gallery"}:
            return

        self.view_mode = mode
        if mode == "single":
            self.viewer_stack.setCurrentIndex(0)
            self._sync_view_toggle_buttons(single_selected=True)
        else:
            self.viewer_stack.setCurrentIndex(1)
            self._sync_view_toggle_buttons(single_selected=False)
            self._refresh_gallery_from_current_image(load=True)

    def _sync_view_toggle_buttons(self, single_selected: bool) -> None:
        """Keep view toggle buttons in sync without recursive signals."""
        if not hasattr(self, "single_view_btn") or not hasattr(self, "gallery_view_btn"):
            return
        self.single_view_btn.blockSignals(True)
        self.gallery_view_btn.blockSignals(True)
        self.single_view_btn.setChecked(single_selected)
        self.gallery_view_btn.setChecked(not single_selected)
        self.single_view_btn.blockSignals(False)
        self.gallery_view_btn.blockSignals(False)

    def _refresh_gallery_from_current_image(self, load: bool | None = None) -> None:
        """Update gallery and optionally load thumbnails for current folder."""
        directory: Path | None = None
        if self.current_image_path and self.current_image_path.exists():
            directory = self.current_image_path.parent
        elif self.current_folder and self.current_folder.exists():
            directory = self.current_folder

        if not directory or not directory.exists():
            self.gallery_grid.clear()
            self.gallery_selection_label.setText("")
            self.delete_selected_btn.setEnabled(False)
            self._append_status("Galerie: Kein gültiges Verzeichnis gefunden.")
            return

        self._gallery_current_directory = directory
        should_load = load if load is not None else self.view_mode == "gallery"
        count = 0
        if should_load:
            try:
                count = self.gallery_grid.load_directory(directory)
                self._append_status(f"Galerie geladen: {directory} ({count} Dateien)")
            except Exception as exc:
                self._append_status(f"Galerie konnte nicht geladen werden: {exc}")
                count = 0

        self._gallery_image_count = count
        self.delete_selected_btn.setEnabled(False)
        self.gallery_grid.viewport().update()

    def _update_gallery_selection_state(self) -> None:
        """Update selection label and delete button state based on grid selection."""
        selection_count = len(self.gallery_grid.selectedItems())
        if selection_count == 0:
            self.gallery_selection_label.setText("")
            self.delete_selected_btn.setEnabled(False)
        else:
            self.gallery_selection_label.setText(f"{selection_count} ausgewählt")
            self.delete_selected_btn.setEnabled(True)
        # Auto-show and update metadata popup in gallery view
        if self.view_mode == "gallery":
            self._show_image_info_dialog(auto=True)

    def _open_image_from_gallery_item(self, item) -> None:
        """Open double-clicked image in single view."""
        if not item:
            return
        path = self.gallery_grid.path_for_item(item)
        if not path:
            return
        self._set_view_mode("single")
        self._handle_file_drop(path)

    def _delete_selected_images(self) -> None:
        """Delete selected images from gallery view."""
        if not hasattr(self, "gallery_grid"):
            return
        paths = self.gallery_grid.selected_paths()
        if not paths:
            return

        count = len(paths)
        confirm = QMessageBox.question(
            self,
            "Auswahl löschen?",
            f"{count} Bild{'er' if count != 1 else ''} dauerhaft löschen?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return

        directory = self.gallery_grid.current_directory or self.current_folder
        deleted: list[Path] = []
        failures: list[str] = []

        for path in paths:
            try:
                if path.exists():
                    path.unlink()
                deleted.append(path)
            except Exception as exc:
                failures.append(f"{path.name}: {exc}")

        if deleted:
            deleted_names = ", ".join(p.name for p in deleted)
            self._append_status(f"Gelöscht: {deleted_names}")
            if self.current_image_path and self.current_image_path in deleted:
                was_gallery = self.view_mode == "gallery"
                self._reset_internal_state()
                self.current_image_path = None
                if directory:
                    self.current_folder = directory
                if was_gallery:
                    self._set_view_mode("gallery")

        if failures:
            self._show_error("Konnte nicht löschen:\n" + "\n".join(failures))

        self._refresh_gallery_from_current_image(load=True)

    def _sync_temperature_slider(self, value: int) -> None:
        if hasattr(self, "temperature_slider"):
            self.temperature_slider.blockSignals(True)
            self.temperature_slider.setValue(value)
            self.temperature_slider.blockSignals(False)
            self.temperature_label.setText(str(value))

    def _sync_rgb_sliders(self, red: int, green: int, blue: int) -> None:
        if hasattr(self, "red_balance_slider"):
            self.red_balance_slider.blockSignals(True)
            self.red_balance_slider.setValue(red)
            self.red_balance_slider.blockSignals(False)
            self.red_balance_label.setText(str(red))

            self.green_balance_slider.blockSignals(True)
            self.green_balance_slider.setValue(green)
            self.green_balance_slider.blockSignals(False)
            self.green_balance_label.setText(str(green))

            self.blue_balance_slider.blockSignals(True)
            self.blue_balance_slider.setValue(blue)
            self.blue_balance_slider.blockSignals(False)
            self.blue_balance_label.setText(str(blue))

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
        self.metadata_dirty = True

    def _load_metadata_info(self, path: Path) -> None:
        try:
            with Image.open(path) as img:
                width, height = img.size
                info = {str(k): str(v) for k, v in img.info.items()}
        except Exception as exc:
            self._append_status(f"Metadaten konnten nicht geladen werden: {exc}")
            width = height = 0
            info = {}
        if hasattr(self, "filename_label"):
            self.filename_label.setText(path.name)
        self.current_resolution = (width, height)
        self.loaded_metadata = info
        metadata_text = "\n".join(f"{k}={v}" for k, v in info.items())
        self.metadata_text = metadata_text
        self.metadata_dirty = False
        self._update_info_dialog()

    def _parse_metadata_text(self) -> dict[str, str]:
        text = self.metadata_text or ""
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

    def _update_info_dialog(self) -> None:
        """Refresh content of the info dialog if it is open."""
        if not (self.info_dialog and self.info_dialog.isVisible() and self.current_image_path):
            return
        info_text = self._build_gallery_info_text() if self.view_mode == "gallery" else self._build_image_info_text()
        edit = self.info_dialog.findChild(QPlainTextEdit)
        if edit:
            edit.setPlainText(info_text)

    def _show_image_info_dialog(self, auto: bool = False) -> None:
        """Display image or gallery info in a popup. Auto mode updates without toggling."""
        # Determine what info to show
        if self.view_mode == "gallery":
            info_text = self._build_gallery_info_text()
            title = "Galerie-Info"
        else:
            if not self.current_image_path:
                if not auto:
                    self._show_error("Bitte zuerst ein Bild laden.")
                return
            info_text = self._build_image_info_text()
            title = "Bild-Info"

        if not info_text:
            if not auto:
                self._show_error("Keine Informationen verfügbar.")
            return

        # If dialog already visible, just update text/position
        if self.info_dialog and self.info_dialog.isVisible():
            edit = self.info_dialog.findChild(QPlainTextEdit)
            if edit:
                edit.setPlainText(info_text)
            self._position_info_dialog(self.info_dialog)
            return

        # Toggle off on manual invocation
        if self.info_dialog and self.info_dialog.isVisible() and not auto:
            self.info_dialog.close()
            self._clear_info_dialog()
            return

        self.info_dialog = QDialog(self)
        self.info_dialog.setWindowTitle(title)
        layout = QVBoxLayout(self.info_dialog)
        text_widget = QPlainTextEdit()
        text_widget.setReadOnly(True)
        text_widget.setPlainText(info_text)
        layout.addWidget(text_widget)
        self.info_dialog.resize(380, 560)
        self._position_info_dialog(self.info_dialog)
        self.info_dialog.finished.connect(lambda _: self._clear_info_dialog())
        self.info_dialog.show()

    def _build_image_info_text(self) -> str:
        """Build info text for current image in single view or selected gallery image."""
        if not self.current_image_path:
            return ""

        width, height = self.current_resolution
        resolution_text = f"{width} × {height}" if width and height else "Unbekannt"
        metadata_body = self.metadata_text.strip() if self.metadata_text else "Keine Metadaten gefunden."

        return "\n".join(
            [
                f"Name: {self.current_image_path.name}",
                f"Pfad: {self.current_image_path}",
                f"Auflösung: {resolution_text}",
                "",
                "Metadaten:",
                metadata_body,
            ]
        )

    def _build_gallery_info_text(self) -> str:
        """Build info text for gallery view."""
        selected_items = self.gallery_grid.selectedItems()

        if not selected_items:
            # No selection: show gallery-wide info
            if not self._gallery_current_directory:
                return "Keine Galerie geladen."

            return "\n".join(
                [
                    f"Galerieordner: {self._gallery_current_directory}",
                    f"Bilder im Ordner: {self._gallery_image_count}",
                    "",
                    "Klicke auf ein Bild, um dessen Details anzuzeigen.",
                ]
            )

        # Selection: show info for selected image(s)
        if len(selected_items) == 1:
            # Single image: show detailed info
            item = selected_items[0]
            image_path = self.gallery_grid.path_for_item(item)
            if not image_path:
                return "Bildinformation nicht verfügbar."

            try:
                with Image.open(image_path) as img:
                    width, height = img.size
                    metadata = {str(k): str(v) for k, v in img.info.items()}
            except Exception:
                width, height = 0, 0
                metadata = {}

            resolution_text = f"{width} × {height}" if width and height else "Unbekannt"
            metadata_body = "\n".join(f"{k}={v}" for k, v in metadata.items()) if metadata else "Keine Metadaten gefunden."

            return "\n".join(
                [
                    f"Name: {image_path.name}",
                    f"Pfad: {image_path}",
                    f"Auflösung: {resolution_text}",
                    "",
                    "Metadaten:",
                    metadata_body,
                ]
            )
        else:
            # Multiple images: show selection summary
            total_size = 0
            try:
                for item in selected_items:
                    image_path = self.gallery_grid.path_for_item(item)
                    if image_path and image_path.exists():
                        total_size += image_path.stat().st_size
            except Exception:
                pass

            size_text = f"{total_size / (1024*1024):.2f} MB" if total_size else "Unbekannt"
            return "\n".join(
                [
                    f"Anzahl ausgewählter Bilder: {len(selected_items)}",
                    f"Gesamtgröße: {size_text}",
                ]
            )

    def _clear_info_dialog(self) -> None:
        """Reset info dialog reference."""
        self.info_dialog = None

    def _position_info_dialog(self, dialog: QDialog) -> None:
        """Place info dialog in the right control area (fits white space)."""
        try:
            # Base dimensions
            dialog_width = dialog.width()
            dialog_height = dialog.height()
            # Top-left of main window in global coords
            top_left = self.mapToGlobal(self.rect().topLeft())
            # Place near right control column, slightly below top buttons
            margin = 12
            x = top_left.x() + self.width() - self.controls_width + margin
            y = top_left.y() + 90  # below top button rows
            dialog.move(max(0, x), max(0, y))
        except Exception:
            pass

    def _build_variant_specs(self, adjusted: Image.Image) -> tuple[list[tuple[str, int, int]], str]:
        return self.session.build_variant_specs(adjusted)

    def _append_status(self, message: str) -> None:
        if hasattr(self, "status_log"):
            self.status_log.appendPlainText(message)
            self.status_log.ensureCursorVisible()
        else:
            print(message)

    def _snapshot_adjustment_state(self) -> AdjustmentState:
        state = self.adjustment_controller.state
        return AdjustmentState(
            brightness=state.brightness,
            contrast=state.contrast,
            saturation=state.saturation,
            sharpness=state.sharpness,
            temperature=state.temperature,
            red_balance=state.red_balance,
            green_balance=state.green_balance,
            blue_balance=state.blue_balance,
        )

    def _reset_internal_state(self, clear_canvas: bool = True) -> None:
        if self.active_ratio_button:
            self.active_ratio_button.setChecked(False)
        self.active_ratio_button = None
        self.has_ratio_selection = False
        self.session = ImageSession(self.settings)
        self.current_adjusted_image = None
        self.crop_geometry = None
        self.view_mode = "single"
        self.current_folder = None
        self.metadata_text = ""
        self.metadata_dirty = False
        self.loaded_metadata = {}
        self._comfy_script = Path.home() / "_AA_ComfyUI" / "start-gui.sh"
        self.current_resolution = (0, 0)
        if clear_canvas:
            self.canvas.clear()
        self.canvas.crop_overlay.clear_selection()
        self.adjustment_controller.reset()
        self._sync_all_sliders()
        self._set_adjustment_controls_enabled(False)
        self._enable_save_buttons(False)
        self._reset_zoom_controls()
        self.balance_mode = 0
        if hasattr(self, "auto_balance_btn"):
            self.auto_balance_btn.setIcon(qta.icon("fa5s.magic", color="white"))
            self.auto_balance_btn.setText("")
        if hasattr(self, "filename_label"):
            self.filename_label.setText("-")
        if hasattr(self, "viewer_stack"):
            self.viewer_stack.setCurrentIndex(0)
        if hasattr(self, "single_view_btn") and hasattr(self, "gallery_view_btn"):
            self.single_view_btn.blockSignals(True)
            self.gallery_view_btn.blockSignals(True)
            self.single_view_btn.setChecked(True)
            self.gallery_view_btn.setChecked(False)
            self.single_view_btn.blockSignals(False)
            self.gallery_view_btn.blockSignals(False)
        if hasattr(self, "gallery_grid"):
            self.gallery_grid.clear()
        if hasattr(self, "gallery_title_label"):
            self.gallery_title_label.setText("Galerieansicht")
        if hasattr(self, "gallery_selection_label"):
            self.gallery_selection_label.setText("")
        if hasattr(self, "delete_selected_btn"):
            self.delete_selected_btn.setEnabled(False)
        self._gallery_current_directory = None
        self._gallery_image_count = 0
        if hasattr(self, "open_in_comfy_btn"):
            self.open_in_comfy_btn.setEnabled(False)
        if self.info_dialog:
            self.info_dialog.close()
            self.info_dialog = None

    def _reset_zoom_controls(self) -> None:
        if hasattr(self, "zoom_controller"):
            self.zoom_controller.reset()
            has_image = self.session.has_image() if hasattr(self, "session") else False
            self.zoom_controller.set_enabled(has_image)

    def closeEvent(self, event) -> None:
        self._reset_internal_state()
        self._append_status("Anwendung geschlossen.")
        super().closeEvent(event)

    def _update_history_actions(self) -> None:
        has_undo = bool(self.image_store.undo_stack)
        has_redo = bool(self.image_store.redo_stack)
        has_original = self.image_store.original is not None

        self.undo_action.setEnabled(has_undo)
        self.redo_action.setEnabled(has_redo)
        self.reset_action.setEnabled(has_original)

        # Update buttons
        if hasattr(self, "undo_btn"):
            self.undo_btn.setEnabled(has_undo)
        if hasattr(self, "redo_btn"):
            self.redo_btn.setEnabled(has_redo)
        if hasattr(self, "reset_original_btn"):
            self.reset_original_btn.setEnabled(has_original)
        self._update_comfy_button_state()

    def _update_comfy_button_state(self) -> None:
        """Enable ComfyUI launch button if image and launcher script are available."""
        enabled = bool(self.current_image_path and self._comfy_script.exists())
        if hasattr(self, "open_in_comfy_btn"):
            self.open_in_comfy_btn.setEnabled(enabled)

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
        if base is not None:
            self.session.set_base_image(base.copy())
            self._set_adjustment_controls_enabled(True)
        else:
            self.session = ImageSession(self.settings)
            self._set_adjustment_controls_enabled(False)

        adj = payload.get("adjustment_state", {})
        restored_state = AdjustmentState(
            brightness=adj.get("brightness", 1.0),
            contrast=adj.get("contrast", 1.0),
            saturation=adj.get("saturation", 1.0),
            sharpness=adj.get("sharpness", 1.0),
            temperature=adj.get("temperature", 0),
            red_balance=adj.get("red_balance", 0),
            green_balance=adj.get("green_balance", 0),
            blue_balance=adj.get("blue_balance", 0),
        )
        self.adjustment_controller.set_state(restored_state)
        self._sync_all_sliders()

        current = payload.get("current_image")
        if current:
            self.current_adjusted_image = current.copy()
            self.canvas.display_pil_image(self.current_adjusted_image)
        else:
            self.current_adjusted_image = None
            self.canvas.clear()
        self.crop_geometry = CropGeometry.from_payload(payload.get("crop_geometry"))

        enabled = self.current_adjusted_image is not None
        self._enable_save_buttons(enabled)
        meta_text = payload.get("metadata_text")
        if meta_text is not None:
            self.metadata_text = meta_text
            self.metadata_dirty = False

    def _has_unsaved_changes(self) -> bool:
        return bool((self.session.has_image() and self.current_adjusted_image) or self.metadata_dirty or self.image_store.has_unsaved_changes())

    def _add_factor_slider(self, parent_layout: QVBoxLayout, field: str, title: str) -> tuple[QSlider, QLabel]:
        container = QVBoxLayout()
        container.setSpacing(2)
        label = QLabel(f"{title}: 1.00")
        slider = QSlider(Qt.Horizontal)
        slider.setRange(20, 200)
        slider.setValue(100)
        slider.valueChanged.connect(
            lambda val, lbl=label, fld=field, ttl=title: self._on_factor_slider_change(fld, ttl, val, lbl)
        )
        slider.sliderReleased.connect(lambda ttl=title: self._commit_factor_state(ttl))
        container.addWidget(label)
        container.addWidget(slider)
        parent_layout.addLayout(container)
        self.adjustment_controls.extend([label, slider])
        return slider, label

    def _add_factor_slider_with_icon(self, parent_layout: QVBoxLayout, field: str, title: str, icon_name: str) -> tuple[QSlider, QLabel]:
        """Add a factor slider with icon instead of text label."""
        container = QHBoxLayout()
        container.setSpacing(4)

        icon_label = QLabel()
        icon_label.setPixmap(qta.icon(icon_name, color="#666").pixmap(20, 20))
        icon_label.setFixedWidth(24)
        icon_label.setToolTip(title)
        container.addWidget(icon_label)

        value_label = QLabel("1.00")
        value_label.setFixedWidth(35)
        container.addWidget(value_label)

        slider = QSlider(Qt.Horizontal)
        slider.setRange(20, 200)
        slider.setValue(100)
        slider.valueChanged.connect(
            lambda val, lbl=value_label, fld=field, ttl=title: self._on_factor_slider_change(fld, ttl, val, lbl)
        )
        slider.sliderReleased.connect(lambda ttl=title: self._commit_factor_state(ttl))
        container.addWidget(slider)

        parent_layout.addLayout(container)
        self.adjustment_controls.extend([value_label, slider])
        return slider, value_label

    def _slider_to_factor(self, slider_value: int) -> float:
        return round(slider_value / 100.0, 2)

    def _factor_to_slider(self, factor: float) -> int:
        return max(20, min(200, int(round(factor * 100))))

    def _sync_all_sliders(self) -> None:
        state = self.adjustment_controller.state
        for field, info in getattr(self, "factor_sliders", {}).items():
            slider = info["slider"]
            label = info["label"]
            title = info["title"]
            value = getattr(state, field)
            self._sync_factor_slider(slider, label, title, value)
        self._sync_temperature_slider(state.temperature)
        self._sync_rgb_sliders(state.red_balance, state.green_balance, state.blue_balance)

    def _sync_factor_slider(self, slider: QSlider, label: QLabel, title: str, value: float) -> None:
        slider.blockSignals(True)
        slider.setValue(self._factor_to_slider(value))
        slider.blockSignals(False)
        label.setText(f"{value:.2f}")

    def _prepare_export_base_image(self) -> Image.Image:
        """Return the current base image for export."""
        return self.session.current_base()

    def _do_export_variants(self, target_path: Path) -> list[Path] | None:
        """
        Common export logic for both export_variants() and _save_variants_as().

        Returns list of exported paths on success, None on error.
        """
        try:
            base_image = self._prepare_export_base_image()
        except ImageSessionError as exc:
            self._show_error(str(exc))
            return None

        adjusted = self.current_adjusted_image
        if adjusted is None or adjusted.size != base_image.size:
            self._append_status("Wende Anpassungen an...")
            adjusted = apply_adjustments(base_image, self.adjustment_controller.state)
            self.current_adjusted_image = adjusted

        specs, ratio_suffix = self._build_variant_specs(adjusted)
        self._append_status(f"Erzeuge {len(specs)} Variante(n)...")
        metadata_dict = self._parse_metadata_text()
        metadata_bytes = self._metadata_to_xmp(metadata_dict)

        variants: list[ExportVariant] = []
        for idx, (prefix, target_width, target_height) in enumerate(specs, 1):
            if target_width == adjusted.width and target_height == adjusted.height:
                self._append_status(f"  [{idx}/{len(specs)}] Original {target_width}x{target_height} (Prefix: '{prefix}')")
                variant_img = adjusted.copy()
            else:
                self._append_status(f"  [{idx}/{len(specs)}] Resize → {target_width}x{target_height} (Prefix: '{prefix}')...")
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
            self._append_status("Schreibe Dateien...")
            paths = self.export_service.export_variants(target_path, variants, metadata_bytes)
        except ExportServiceError as exc:
            self._show_error(str(exc))
            return None

        return paths

    def _save_simple(self) -> None:
        """Save current adjusted image to original file (overwrite)."""
        if not self.image_store.current or not self.session.has_image():
            self._show_error("Bitte zuerst ein Bild laden.")
            return

        # Apply crop if ratio selection is active
        if self.has_ratio_selection and self.current_adjusted_image is None:
            self.apply_crop()

        # Prepare image: apply adjustments if not already done
        if self.current_adjusted_image is None:
            try:
                image_to_save = self.session.apply_adjustments(self.adjustment_controller.state)
            except Exception as exc:
                self._show_error(f"Fehler beim Anwenden der Anpassungen: {exc}")
                return
        else:
            image_to_save = self.current_adjusted_image

        target_path = self.image_store.current.path

        # Confirm overwrite
        confirm = QMessageBox.question(
            self,
            "Original überschreiben?",
            f"Datei wird überschrieben:\n{target_path.name}\n\nFortfahren?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return

        try:
            self._append_status(f"Speichere: {target_path.name}")

            # Determine format and save parameters
            suffix = target_path.suffix.lower()
            save_kwargs = {}

            if suffix in {".jpg", ".jpeg"}:
                if image_to_save.mode == "RGBA":
                    image_to_save = image_to_save.convert("RGB")
                save_kwargs = {"quality": self.settings.export.quality}
            elif suffix == ".webp":
                save_kwargs = {"quality": self.settings.export.quality, "method": 6}
            elif suffix == ".png":
                save_kwargs = {"compress_level": 6}

            image_to_save.save(target_path, **save_kwargs)

            self.metadata_dirty = False
            self.status_bar.showMessage(f"Gespeichert: {target_path.name}", 5000)
            self._append_status(f"✓ Bild gespeichert: {target_path.name}")

            # Update last exported paths for results viewer
            self.last_exported_paths = [target_path]
            if hasattr(self, "view_results_btn"):
                self.view_results_btn.setEnabled(True)

        except Exception as exc:
            self.logger.exception("Fehler beim Speichern")
            self._show_error(f"Fehler beim Speichern: {exc}")
            self._append_status(f"✗ Fehler: {exc}")

    def export_variants(self) -> None:
        if self.current_adjusted_image is None and self.has_ratio_selection:
            self.apply_crop()

        if not self.image_store.current or not self.session.has_image():
            self._show_error("Keine Varianten zum Export vorhanden.")
            return

        self._append_status("=== Varianten-Export gestartet ===")

        paths = self._do_export_variants(self.image_store.current.path)
        if not paths:
            return

        names = ", ".join(path.name for path in paths)
        self.metadata_dirty = False
        self.status_bar.showMessage(f"Exportiert: {names}", 7000)
        self._append_status("✓ Varianten gespeichert: " + ", ".join(str(p) for p in paths))
        self._append_status("=== Varianten-Export abgeschlossen ===")

        # Save paths and enable results viewer + save as button
        self.last_exported_paths = paths
        if hasattr(self, "view_results_btn"):
            self.view_results_btn.setEnabled(True)
        if hasattr(self, "save_as_btn"):
            self.save_as_btn.setEnabled(True)

    def _save_variants_as(self) -> None:
        """Save with custom resolution and format."""
        if not self.session.has_image():
            self._show_error("Bitte zuerst ein Bild laden.")
            return

        # Apply crop if ratio selection is active (same as export_variants)
        if self.current_adjusted_image is None and self.has_ratio_selection:
            self.apply_crop()

        # Get current image dimensions
        if self.current_adjusted_image:
            source_width = self.current_adjusted_image.width
            source_height = self.current_adjusted_image.height
        else:
            base = self.session.current_base()
            source_width = base.width
            source_height = base.height

        # Suggested path
        suggested_path = None
        if self.image_store.current:
            suggested_path = self.image_store.current.path.parent / (
                self.image_store.current.path.stem + ".webp"
            )

        # Show dialog
        dialog = SaveAsDialog(
            self,
            source_width=source_width,
            source_height=source_height,
            suggested_path=suggested_path,
        )

        self._append_status("=== Save As Dialog geöffnet ===")
        exec_result = dialog.exec()
        self._append_status(f"Dialog exec() Ergebnis: {exec_result} (Accepted={QDialog.DialogCode.Accepted})")
        self._append_status(f"Dialog result Objekt: {dialog.result}")

        if exec_result != QDialog.DialogCode.Accepted or not dialog.result:
            self._append_status("Dialog abgebrochen oder kein Ergebnis")
            return

        result = dialog.result
        self._append_status(f"=== Speichern unter: {result.path} ===")
        self._append_status(f"Auflösung: {result.width}x{result.height}, Format: {result.format.upper()}")

        # Prepare image
        self._append_status("Bereite Bild für Export vor...")
        if self.current_adjusted_image:
            source_image = self.current_adjusted_image
            self._append_status(f"Verwende aktuell angepasstes Bild: {source_image.width}x{source_image.height}")
        else:
            self._append_status("Wende Anpassungen auf Basisbild an...")
            source_image = apply_adjustments(
                self.session.current_base(),
                self.adjustment_controller.state
            )
            self.current_adjusted_image = source_image
            self._append_status(f"Angepasstes Bild erstellt: {source_image.width}x{source_image.height}")

        # Resize if needed
        if result.width != source_image.width or result.height != source_image.height:
            self._append_status(f"Skaliere {source_image.width}x{source_image.height} -> {result.width}x{result.height}...")
            output_image = self.processing_pipeline.resize_with_quality(
                source_image,
                target_width=result.width,
                target_height=result.height,
            )
            self._append_status(f"✓ Skalierung abgeschlossen: {output_image.width}x{output_image.height}")
        else:
            output_image = source_image.copy()
            self._append_status("Keine Skalierung nötig, verwende Original-Auflösung")

        # Save with correct format
        try:
            self._append_status(f"Erstelle Zielverzeichnis: {result.path.parent}")
            result.path.parent.mkdir(parents=True, exist_ok=True)

            save_kwargs = {}
            if result.format == "webp":
                save_kwargs = {"quality": self.settings.export.quality, "method": 6}
                self._append_status(f"Format: WebP, Quality={self.settings.export.quality}")
            elif result.format == "jpeg":
                save_kwargs = {"quality": self.settings.export.quality}
                self._append_status(f"Format: JPEG, Quality={self.settings.export.quality}")
            elif result.format == "png":
                save_kwargs = {"compress_level": 6}
                self._append_status("Format: PNG, Compress Level=6")

            # Convert to RGB for JPEG if needed
            if result.format == "jpeg" and output_image.mode == "RGBA":
                self._append_status("Konvertiere RGBA zu RGB für JPEG...")
                output_image = output_image.convert("RGB")

            self._append_status(f"Speichere Datei: {result.path}")
            output_image.save(result.path, **save_kwargs)
            self._append_status(f"✓ Datei erfolgreich gespeichert: {result.path}")
            self.status_bar.showMessage(f"Gespeichert: {result.path.name}", 7000)

            # Update last exported paths and enable results viewer
            self.last_exported_paths = [result.path]
            if hasattr(self, "view_results_btn"):
                self.view_results_btn.setEnabled(True)

        except Exception as exc:
            self.logger.exception("Fehler beim Speichern")
            self._show_error(f"Fehler beim Speichern: {exc}")
            self._append_status(f"✗ Fehler: {exc}")

    # --- Image Navigation ---------------------------------------------------
    def _get_sibling_images(self) -> tuple[Path | None, Path | None]:
        """Get previous and next image paths in current directory."""
        if not self.current_image_path:
            return None, None

        directory = self.current_image_path.parent
        current_name = self.current_image_path.name

        image_files = self._list_image_files(directory)

        if not image_files:
            return None, None

        # Find current image index
        try:
            current_idx = next(i for i, p in enumerate(image_files) if p.name == current_name)
        except StopIteration:
            return None, None

        prev_path = image_files[current_idx - 1] if current_idx > 0 else None
        next_path = image_files[current_idx + 1] if current_idx < len(image_files) - 1 else None

        return prev_path, next_path

    def _list_image_files(self, directory: Path) -> list[Path]:
        """Return sorted list of image files in directory."""
        if not directory or not directory.exists():
            return []
        image_files: list[Path] = []
        for ext in SUPPORTED_EXTENSIONS:
            image_files.extend(directory.glob(f"*{ext}"))
            image_files.extend(directory.glob(f"*{ext.upper()}"))
        image_files = sorted(set(image_files), key=lambda p: p.name.lower())
        return image_files

    def _update_navigation_buttons(self) -> None:
        """Update navigation button states based on available sibling images."""
        prev_path, next_path = self._get_sibling_images()
        self.canvas.set_navigation_enabled(prev_path is not None, next_path is not None)

    def _navigate_to_previous_image(self) -> None:
        """Navigate to previous image in directory."""
        prev_path, _ = self._get_sibling_images()
        if prev_path:
            self._handle_file_drop(prev_path)

    def _navigate_to_next_image(self) -> None:
        """Navigate to next image in directory."""
        _, next_path = self._get_sibling_images()
        if next_path:
            self._handle_file_drop(next_path)

    # --- Recent Files/Folders -------------------------------------------------
    def _show_recent_images_menu(self) -> None:
        """Show dropdown menu with recent images."""
        menu = QMenu(self)
        recent_files = self.recent_manager.recent_files()

        if not recent_files:
            action = menu.addAction("Keine zuletzt geöffneten Bilder")
            action.setEnabled(False)
        else:
            for path in recent_files:
                action = menu.addAction(f"{path.name}  ({path.parent.name})")
                action.setData(path)
                action.triggered.connect(lambda checked, p=path: self._handle_file_drop(p))

        # Position menu below button
        btn = self.recent_images_btn
        pos = btn.mapToGlobal(btn.rect().bottomLeft())
        menu.exec(pos)

    def _show_recent_folders_menu(self) -> None:
        """Show dropdown menu with recent folders."""
        menu = QMenu(self)
        recent_folders = self.recent_manager.recent_folders()

        if not recent_folders:
            action = menu.addAction("Keine zuletzt geöffneten Ordner")
            action.setEnabled(False)
        else:
            for path in recent_folders:
                action = menu.addAction(f"{path.name}  ({path.parent.name})")
                action.setData(path)
                action.triggered.connect(lambda checked, p=path: self._open_recent_folder(p))

        # Position menu below button
        btn = self.recent_folders_btn
        pos = btn.mapToGlobal(btn.rect().bottomLeft())
        menu.exec(pos)

    def _open_recent_folder(self, folder_path: Path) -> None:
        """Open file browser and navigate to the folder."""
        if not folder_path.exists():
            self._show_error(f"Ordner existiert nicht mehr:\n{folder_path}")
            return

        # Show file browser and navigate to folder
        self.toggle_browser_btn.setChecked(True)
        self._toggle_file_browser(True)
        self.file_browser.file_tree.navigate_to(folder_path)
