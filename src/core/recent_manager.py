"""
Recent files and folders manager with persistent storage.

Separation of Concerns: Handles only recent items persistence.
KISS: Simple JSON file storage.
Fail Fast: Validates paths exist before adding.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

MAX_RECENT_ITEMS = 15
RECENT_FILE_NAME = ".image_processor_recent.json"


class RecentManager:
    """Manages recently used files and folders with JSON persistence."""

    def __init__(self, storage_dir: Optional[Path] = None) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self._storage_dir = storage_dir or Path.home()
        self._storage_path = self._storage_dir / RECENT_FILE_NAME
        self._recent_files: list[Path] = []
        self._recent_folders: list[Path] = []
        self._load()

    def _load(self) -> None:
        """Load recent items from JSON file."""
        if not self._storage_path.exists():
            return

        try:
            with open(self._storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Load files (filter out non-existent)
            for path_str in data.get("files", []):
                path = Path(path_str)
                if path.exists() and path.is_file():
                    self._recent_files.append(path)

            # Load folders (filter out non-existent)
            for path_str in data.get("folders", []):
                path = Path(path_str)
                if path.exists() and path.is_dir():
                    self._recent_folders.append(path)

            self.logger.debug("Loaded %d recent files, %d recent folders",
                              len(self._recent_files), len(self._recent_folders))
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            self.logger.warning("Failed to load recent items: %s", exc)

    def _save(self) -> None:
        """Save recent items to JSON file."""
        data = {
            "files": [str(p) for p in self._recent_files],
            "folders": [str(p) for p in self._recent_folders],
        }
        try:
            with open(self._storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except OSError as exc:
            self.logger.warning("Failed to save recent items: %s", exc)

    def add_file(self, path: Path) -> None:
        """Add a file to recent files list."""
        if not path.exists() or not path.is_file():
            return

        # Remove if already in list (will be re-added at top)
        path = path.resolve()
        self._recent_files = [p for p in self._recent_files if p != path]

        # Add at beginning
        self._recent_files.insert(0, path)

        # Trim to max size
        self._recent_files = self._recent_files[:MAX_RECENT_ITEMS]

        self._save()

    def add_folder(self, path: Path) -> None:
        """Add a folder to recent folders list."""
        if not path.exists() or not path.is_dir():
            return

        # Remove if already in list (will be re-added at top)
        path = path.resolve()
        self._recent_folders = [p for p in self._recent_folders if p != path]

        # Add at beginning
        self._recent_folders.insert(0, path)

        # Trim to max size
        self._recent_folders = self._recent_folders[:MAX_RECENT_ITEMS]

        self._save()

    def recent_files(self) -> list[Path]:
        """Return list of recent files (most recent first)."""
        # Filter out any that no longer exist
        valid = [p for p in self._recent_files if p.exists()]
        if len(valid) != len(self._recent_files):
            self._recent_files = valid
            self._save()
        return list(valid)

    def recent_folders(self) -> list[Path]:
        """Return list of recent folders (most recent first)."""
        # Filter out any that no longer exist
        valid = [p for p in self._recent_folders if p.exists()]
        if len(valid) != len(self._recent_folders):
            self._recent_folders = valid
            self._save()
        return list(valid)

    def clear_files(self) -> None:
        """Clear all recent files."""
        self._recent_files = []
        self._save()

    def clear_folders(self) -> None:
        """Clear all recent folders."""
        self._recent_folders = []
        self._save()
