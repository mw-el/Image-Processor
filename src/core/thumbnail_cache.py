from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional
from PIL import Image

THUMBNAIL_SIZE = 256


class ThumbnailCache:
    """
    Manages thumbnail generation and caching following freedesktop.org standard.
    Thumbnails stored in ~/.cache/thumbnails/normal/ (256x256).

    Separation of Concerns: Pure cache logic, no UI dependencies.
    Fail Fast: Validates paths before access, clear errors on failures.
    KISS: Simple file-based cache, no database.
    """

    def __init__(self, cache_dir: Optional[Path] = None) -> None:
        if cache_dir is None:
            cache_dir = Path.home() / ".cache" / "thumbnails" / "normal"

        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_thumbnail_path(self, image_path: Path) -> Path:
        """Generate cache path using MD5 of absolute URI (freedesktop.org standard)."""
        # Fail Fast: Validate path
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        # freedesktop.org: MD5 of file:// URI
        uri = f"file://{image_path.absolute()}"
        md5_hash = hashlib.md5(uri.encode()).hexdigest()
        return self.cache_dir / f"{md5_hash}.png"

    def get_thumbnail(self, image_path: Path) -> Optional[Path]:
        """
        Get cached thumbnail if exists and is valid.
        Returns None if cache miss or invalid.
        """
        try:
            thumb_path = self.get_thumbnail_path(image_path)

            # Check if cached thumbnail exists
            if not thumb_path.exists():
                return None

            # Validate: thumbnail should be newer than original
            if thumb_path.stat().st_mtime < image_path.stat().st_mtime:
                # Original was modified, cache invalid
                thumb_path.unlink(missing_ok=True)
                return None

            return thumb_path

        except Exception:
            # Fail Fast: Any error → cache miss
            return None

    def create_thumbnail(self, image_path: Path) -> Optional[Path]:
        """
        Create thumbnail from image and cache it.
        Returns path to cached thumbnail or None on failure.

        KISS: Simple PIL thumbnail generation.
        """
        # Fail Fast: Validate
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        if not image_path.is_file():
            raise ValueError(f"Not a file: {image_path}")

        try:
            # Generate thumbnail
            with Image.open(image_path) as img:
                # Convert to RGB for consistent format
                img = img.convert("RGB")

                # Create thumbnail (maintains aspect ratio)
                img.thumbnail((THUMBNAIL_SIZE, THUMBNAIL_SIZE), Image.Resampling.LANCZOS)

                # Save to cache
                thumb_path = self.get_thumbnail_path(image_path)
                img.save(thumb_path, "PNG")

                return thumb_path

        except Exception as e:
            # Fail Fast: Log error and return None
            print(f"Failed to create thumbnail for {image_path}: {e}")
            return None

    def get_or_create_thumbnail(self, image_path: Path) -> Optional[Path]:
        """
        Get cached thumbnail or create if missing.
        Main entry point for thumbnail retrieval.
        """
        # Try cache first
        cached = self.get_thumbnail(image_path)
        if cached:
            return cached

        # Cache miss → create
        return self.create_thumbnail(image_path)

    def clear_cache(self) -> None:
        """Clear all cached thumbnails."""
        for thumb in self.cache_dir.glob("*.png"):
            thumb.unlink(missing_ok=True)
