"""Scan media directories for supported files (recursive)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from src.config import AUDIO_EXTS, VIDEO_EXTS
from src.metadata_store import (
    find_cover_image,
    read_embedded_metadata,
    read_video_thumbnail,
    resolve_display,
)
from src.settings_store import get_music_dir, get_playlist_dir, get_video_dir
from src.models import MediaInfo, MediaKind


def _media_from_file(path: Path, *, audio_only: bool) -> MediaInfo:
    embedded = read_embedded_metadata(path) if audio_only else {}
    detected_image = embedded.get("image", "") if audio_only else read_video_thumbnail(path)
    display = resolve_display(
        str(path.resolve()),
        default_title=embedded.get("title") or path.stem,
        default_artist=embedded.get("artist") or ("Music" if audio_only else "Video"),
        default_image=detected_image,
    )
    return MediaInfo(
        path=str(path.resolve()),
        title=display["title"],
        artist=display["artist"],
        image=display["image"],
        kind=MediaKind.FILE,
    )


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
        audio_only = f.suffix.lower() in AUDIO_EXTS
        files.append(_media_from_file(f, audio_only=audio_only))

    for i, m in enumerate(files, start=1):
        m.num = str(i)

    return files[:limit] if limit else files


def scan_music() -> list[MediaInfo]:
    """Scan configured music directory."""
    return scan_directory(get_music_dir(), AUDIO_EXTS)


def scan_video() -> list[MediaInfo]:
    """Scan configured video directory."""
    return scan_directory(get_video_dir(), VIDEO_EXTS)


def _count_media_in_tree(directory: Path, extensions: set[str]) -> int:
    count = 0
    for f in directory.rglob("*"):
        if f.is_file() and f.suffix.lower() in extensions:
            count += 1
    return count


def _scan_playlist_folder(folder: Path) -> list[MediaInfo]:
    """Scan one playlist directory level: subfolders as albums/playlists + root files."""
    if not folder.exists():
        return []

    items: list[MediaInfo] = []

    for child in sorted(folder.iterdir()):
        if child.is_dir():
            audio_count = _count_media_in_tree(child, AUDIO_EXTS)
            video_count = _count_media_in_tree(child, VIDEO_EXTS)
            if audio_count == 0 and video_count == 0:
                continue

            if video_count > 0 and audio_count == 0:
                kind = MediaKind.VIDEO_PLAYLIST
                subtitle = f"{video_count} video"
                child_count = video_count
            elif audio_count > 0 and video_count == 0:
                kind = MediaKind.ALBUM
                subtitle = f"{audio_count} bài"
                child_count = audio_count
            elif audio_count >= video_count:
                kind = MediaKind.ALBUM
                subtitle = f"{audio_count} bài · {video_count} video"
                child_count = audio_count + video_count
            else:
                kind = MediaKind.VIDEO_PLAYLIST
                subtitle = f"{video_count} video · {audio_count} bài"
                child_count = audio_count + video_count

            display = resolve_display(
                str(child.resolve()),
                default_title=child.name,
                default_artist=subtitle,
            )
            items.append(
                MediaInfo(
                    path=str(child.resolve()),
                    title=display["title"],
                    artist=display["artist"] if display["artist"] != "Unknown Artist" else subtitle,
                    image=display["image"] or find_cover_image(child),
                    kind=kind,
                    child_count=child_count,
                )
            )
            continue

        if child.is_file():
            ext = child.suffix.lower()
            if ext in AUDIO_EXTS:
                items.append(_media_from_file(child, audio_only=True))
            elif ext in VIDEO_EXTS:
                items.append(_media_from_file(child, audio_only=False))

    for i, item in enumerate(items, start=1):
        item.num = str(i)

    return items


def scan_playlist(folder: Path | None = None) -> list[MediaInfo]:
    """Scan playlist directory at one level (collections + root files)."""
    directory = folder or get_playlist_dir()
    return _scan_playlist_folder(directory)


def scan_playlist_recursive() -> list[MediaInfo]:
    """Legacy flat scan of entire playlist tree (audio + video)."""
    directory = get_playlist_dir()
    extensions = AUDIO_EXTS | VIDEO_EXTS
    return scan_directory(directory, extensions)
