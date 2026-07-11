"""Symlink-based multi-album membership without duplicating audio files."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from src.config import AUDIO_EXTS, VIDEO_EXTS

MEDIA_EXTS = AUDIO_EXTS | VIDEO_EXTS


def canonical_path(path: Path) -> Path:
    """Resolve *path* to the real media file (follow symlinks)."""
    try:
        return path.resolve()
    except OSError:
        return path


def is_symlink_entry(path: Path) -> bool:
    return path.is_symlink()


def playlist_contains_media(playlist_dir: Path, canonical: Path) -> bool:
    """Return True if *playlist_dir* already lists this media file (by resolved path)."""
    if not playlist_dir.is_dir():
        return False
    target = canonical_path(canonical)
    for child in playlist_dir.iterdir():
        if child.name.startswith("."):
            continue
        if not child.is_file() or child.suffix.lower() not in MEDIA_EXTS:
            continue
        try:
            if canonical_path(child) == target:
                return True
        except OSError:
            continue
    return False


def album_contains_track(playlist_dir: Path, canonical: Path) -> bool:
    """Backward-compatible alias for audio playlist membership checks."""
    return playlist_contains_media(playlist_dir, canonical)


def _symlink_target(canonical: Path, link_dir: Path) -> str:
    """Prefer a relative symlink target for portability."""
    return os.path.relpath(str(canonical), str(link_dir))


def add_track_to_album(source_entry: Path, album_dir: Path) -> Path | None:
    """Add *source_entry* to *album_dir* via symlink. Returns the link path."""
    if not album_dir.is_dir():
        return None
    canonical = canonical_path(source_entry)
    if not canonical.is_file():
        return None
    if album_contains_track(album_dir, canonical):
        return album_dir / source_entry.name

    link_path = album_dir / source_entry.name
    if link_path.exists():
        return None

    try:
        link_path.symlink_to(_symlink_target(canonical, album_dir))
    except OSError:
        return None
    return link_path


def find_symlinks_to(canonical: Path, search_root: Path) -> list[Path]:
    """Return symlink entries under *search_root* that resolve to *canonical*."""
    target = canonical_path(canonical)
    refs: list[Path] = []
    if not search_root.is_dir():
        return refs
    for entry in search_root.rglob("*"):
        if not entry.is_symlink():
            continue
        try:
            if canonical_path(entry) == target:
                refs.append(entry)
        except OSError:
            continue
    return refs


def _refresh_symlinks(links: list[Path], canonical: Path) -> None:
    """Recreate *links* so they point at *canonical*."""
    for link in links:
        try:
            if link.exists() or link.is_symlink():
                link.unlink()
            link.symlink_to(_symlink_target(canonical, link.parent))
        except OSError:
            continue


def remove_track_from_album(entry: Path, album_dir: Path, library_root: Path) -> bool:
    """Remove *entry* from *album_dir* without deleting other album memberships."""
    try:
        entry = entry if entry.is_absolute() else entry.resolve()
        album_resolved = album_dir.resolve()
        library_root = library_root.resolve()
    except OSError:
        return False

    if not entry.exists() and not entry.is_symlink():
        return False

    if entry.is_symlink():
        try:
            if entry.parent.resolve() != album_resolved:
                return False
            entry.unlink()
            return True
        except OSError:
            return False

    try:
        if entry.parent.resolve() != album_resolved:
            return False
    except OSError:
        return False

    canonical = canonical_path(entry)
    other_links = [
        link
        for link in find_symlinks_to(canonical, library_root)
        if link.parent.resolve() != album_resolved
    ]

    if not other_links:
        dest = library_root / entry.name
        if dest.exists():
            return False
        try:
            shutil.move(str(entry), str(dest))
        except OSError:
            return False
        return True

    dest = library_root / entry.name
    if dest.exists():
        try:
            if canonical_path(dest) != canonical:
                return False
        except OSError:
            return False
    else:
        try:
            shutil.move(str(entry), str(dest))
        except OSError:
            return False

    _refresh_symlinks(other_links, dest)
    return True


def delete_track_completely(entry: Path, library_root: Path) -> bool:
    """Delete the canonical audio file and every album symlink referencing it."""
    try:
        canonical = canonical_path(entry)
    except OSError:
        return False

    for link in find_symlinks_to(canonical, library_root):
        try:
            link.unlink()
        except OSError:
            continue

    try:
        if canonical.is_file() and not canonical.is_symlink():
            canonical.unlink()
        elif entry.exists() or entry.is_symlink():
            entry.unlink()
    except OSError:
        return False
    return True
