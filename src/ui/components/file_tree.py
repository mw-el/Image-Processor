from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import QTreeView, QFileSystemModel
from PySide6.QtCore import Signal, QDir


class FileTreeView(QTreeView):
    """
    Directory tree view starting from HOME directory.

    Separation of Concerns: Pure UI component, emits signals for controller.
    KISS: Uses Qt's QFileSystemModel (no custom implementation).
    """

    # Signal emitted when directory is selected
    directory_selected = Signal(Path)

    def __init__(self, parent=None, start_path: Optional[Path] = None) -> None:
        super().__init__(parent)

        # Start at HOME by default
        if start_path is None:
            start_path = Path.home()

        # Setup file system model (directories only)
        self.model = QFileSystemModel()
        self.model.setRootPath(str(start_path))
        self.model.setFilter(QDir.Dirs | QDir.NoDotAndDotDot)

        # Apply model
        self.setModel(self.model)
        self.setRootIndex(self.model.index(str(start_path)))

        # Hide unnecessary columns (keep only Name)
        self.setColumnHidden(1, True)  # Size
        self.setColumnHidden(2, True)  # Type
        self.setColumnHidden(3, True)  # Date Modified

        # Styling
        self.setHeaderHidden(True)
        self.setAnimated(True)
        self.setIndentation(20)
        self.setExpandsOnDoubleClick(True)

        # Connect selection signal
        self.clicked.connect(self._on_clicked)

    def _on_clicked(self, index) -> None:
        """Handle directory click."""
        # Get path from index
        path_str = self.model.filePath(index)
        path = Path(path_str)

        # Fail Fast: Validate
        if not path.exists() or not path.is_dir():
            return

        # Emit signal
        self.directory_selected.emit(path)

    def set_root_path(self, path: Path) -> None:
        """Change root directory."""
        if not path.exists() or not path.is_dir():
            raise ValueError(f"Invalid directory: {path}")

        self.model.setRootPath(str(path))
        self.setRootIndex(self.model.index(str(path)))

    def navigate_to(self, path: Path) -> None:
        """Navigate to and select a specific directory."""
        if not path.exists() or not path.is_dir():
            return

        index = self.model.index(str(path))
        if index.isValid():
            self.setCurrentIndex(index)
            self.scrollTo(index)
            self.expand(index)
            # Emit signal to load thumbnails
            self.directory_selected.emit(path)
