import logging
import sys
from pathlib import Path


def configure_logging(log_dir: Path | None = None) -> None:
    """
    Configure application-wide logging with console + file handlers.

    Fail-fast principle: logs errors immediately with stack traces while keeping
    configuration simple and centralized.
    """
    log_dir = log_dir or Path.home() / ".aa_image_processor"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "app.log"

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s – %(message)s", "%Y-%m-%d %H:%M:%S"
    )

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    logging.basicConfig(level=logging.DEBUG, handlers=[file_handler, console_handler], force=True)
