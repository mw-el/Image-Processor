from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from .core.logger import configure_logging
from .core.settings import load_settings
from .ui.main_window import MainWindow


def _load_stylesheet() -> str:
    theme_path = Path(__file__).parent / "ui" / "themes" / "titica_bootstrap.qss"
    if not theme_path.exists():
        return ""
    return theme_path.read_text(encoding="utf-8")


def _load_icon() -> QIcon | None:
    icon_path = Path(__file__).resolve().parents[1] / "image_processor.png"
    if icon_path.exists():
        return QIcon(str(icon_path))
    return None


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AA Image Processor")
    parser.add_argument(
        "image",
        nargs="?",
        help="Optional Pfad zu einer Bilddatei, die beim Start geöffnet wird.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    settings = load_settings()
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    initial_path = Path(args.image).expanduser() if args.image else None

    app = QApplication(sys.argv)
    app.setApplicationName("AA Image Processor")
    app.setOrganizationName("AA Tools")
    app.setDesktopFileName("aa-image-processor")
    app.setStyleSheet(_load_stylesheet())
    icon = _load_icon()
    if icon:
        app.setWindowIcon(icon)

    if initial_path and not initial_path.exists():
        initial_path = None

    window = MainWindow(settings, initial_path=initial_path)
    if icon:
        window.setWindowIcon(icon)
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
