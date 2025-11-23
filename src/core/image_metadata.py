from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
from PIL import Image


@dataclass
class ImageMetadata:
    """Image metadata for tooltips and display."""
    filename: str
    file_type: str
    file_size: str
    dimensions: str
    modified: str

    def to_tooltip_html(self) -> str:
        """Generate HTML tooltip text."""
        return f"""<html>
<b>{self.filename}</b><br>
<b>Type:</b> {self.file_type}<br>
<b>Size:</b> {self.file_size}<br>
<b>Dimensions:</b> {self.dimensions}<br>
<b>Modified:</b> {self.modified}
</html>"""


def extract_image_metadata(image_path: Path) -> ImageMetadata:
    """
    Extract metadata from image file.

    Fail Fast: Raises FileNotFoundError if path doesn't exist.
    KISS: Simple PIL + os.stat, no EXIF parsing (can add later).
    """
    # Fail Fast: Validate
    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    # Get file stats
    stat = image_path.stat()
    file_size_mb = stat.st_size / (1024 * 1024)
    modified_dt = datetime.fromtimestamp(stat.st_mtime)

    # Format file size
    if file_size_mb < 1:
        file_size_str = f"{stat.st_size / 1024:.1f} KB"
    else:
        file_size_str = f"{file_size_mb:.2f} MB"

    # Get image dimensions
    try:
        with Image.open(image_path) as img:
            width, height = img.size
            dimensions_str = f"{width} × {height}"
            file_type = img.format or image_path.suffix[1:].upper()
    except Exception:
        # Fallback if PIL can't open
        dimensions_str = "Unknown"
        file_type = image_path.suffix[1:].upper() if image_path.suffix else "Unknown"

    return ImageMetadata(
        filename=image_path.name,
        file_type=file_type,
        file_size=file_size_str,
        dimensions=dimensions_str,
        modified=modified_dt.strftime("%Y-%m-%d %H:%M"),
    )
