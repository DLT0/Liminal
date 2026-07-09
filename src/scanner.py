"""Scan media directories for supported files (recursive)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from src.config import AUDIO_EXTS, VIDEO_EXTS, MUSIC_DIR, VIDEO_DIR
from src.models import MediaInfo


def scan_directory(
    directory: Path,
    extensions: set[str],
    limit: Optional[int] = None,
) -> list[MediaInfo]:
    """Recursively scan *directory* for media files with given extensions.

    Returns sorted list of ``MediaInfo`` objects.
    """
    if not directory.exists():
        return []

    files: list[MediaInfo] = []
    for f in sorted(directory.rglob("*")):
        if not f.is_file() or f.suffix.lower() not in extensions:
            continue
        files.append(
            MediaInfo(
                path=str(f),
                title=f.stem,
                num="0",
            )
        )

    # Re-number
    for i, m in enumerate(files, start=1):
        m.num = str(i)

    return files[:limit] if limit else files


def scan_music() -> list[MediaInfo]:
    """Scan configured music directory."""
    return scan_directory(MUSIC_DIR, AUDIO_EXTS)


def scan_video() -> list[MediaInfo]:
    """Scan configured video directory."""
    return scan_directory(VIDEO_DIR, VIDEO_EXTS)
