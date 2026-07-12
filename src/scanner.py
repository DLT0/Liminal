"""Scan media directories for supported files (recursive)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from src.config import AUDIO_EXTS, VIDEO_EXTS
from src.folder_order import apply_order
from src.metadata_store import (
    find_cover_image,
    read_embedded_metadata,
    read_video_thumbnail,
    resolve_display,
)
from src.settings_store import get_books_dir, get_music_dir, get_video_dir
from src.models import MediaInfo, MediaKind


def _entry_path(path: Path) -> str:
    """Filesystem path used for folder order and album membership operations."""
    try:
        return str(path)
    except OSError:
        return str(path)


def _media_from_file(path: Path, *, audio_only: bool) -> MediaInfo:
    try:
        resolved = path.resolve()
    except OSError:
        resolved = path
    embedded = read_embedded_metadata(resolved) if audio_only else {}
    detected_image = embedded.get("image", "") if audio_only else read_video_thumbnail(resolved)
    display = resolve_display(
        str(resolved),
        default_title=embedded.get("title") or resolved.stem,
        default_artist=embedded.get("artist") or ("Music" if audio_only else "Video"),
        default_image=detected_image,
    )
    return MediaInfo(
        path=_entry_path(path),
        title=display["title"],
        artist=display["artist"],
        image=display["image"],
        kind=MediaKind.FILE,
        canonical_path=str(resolved),
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
    """Scan configured music directory (one level at root)."""
    return scan_library_folder(get_music_dir())


def scan_video() -> list[MediaInfo]:
    """Scan configured video directory (one level at root)."""
    return scan_library_folder(get_video_dir())


def scan_books() -> list[MediaInfo]:
    """Scan configured books directory (one level at root)."""
    return scan_library_folder(get_books_dir())


def _count_media_in_tree(directory: Path, extensions: set[str]) -> int:
    count = 0
    for f in directory.rglob("*"):
        if f.is_file() and f.suffix.lower() in extensions:
            count += 1
    return count


def _first_media_file(directory: Path, extensions: set[str]) -> Path | None:
    for f in sorted(directory.rglob("*")):
        if f.is_file() and f.suffix.lower() in extensions:
            return f
    return None


def find_folder_track_thumbnails(directory: Path, limit: int = 4) -> list[str]:
    """Return up to *limit* distinct cover/thumbnail paths from media inside *directory*."""
    images: list[str] = []
    seen: set[str] = set()

    for f in sorted(directory.rglob("*")):
        if not f.is_file():
            continue
        ext = f.suffix.lower()
        img = ""
        if ext in AUDIO_EXTS:
            embedded = read_embedded_metadata(f)
            display = resolve_display(
                str(f.resolve()),
                default_title=embedded.get("title") or f.stem,
                default_artist=embedded.get("artist") or "Music",
                default_image=embedded.get("image", ""),
            )
            img = display["image"]
        elif ext in VIDEO_EXTS:
            display = resolve_display(
                str(f.resolve()),
                default_title=f.stem,
                default_artist="Video",
                default_image=read_video_thumbnail(f),
            )
            img = display["image"]

        if img and img not in seen:
            images.append(img)
            seen.add(img)
        if len(images) >= limit:
            break

    return images


def find_folder_preview_image(directory: Path) -> str:
    """Windows-style folder preview: first video frame, else first audio cover."""
    cover = find_cover_image(directory)
    if cover:
        return cover

    video = _first_media_file(directory, VIDEO_EXTS)
    if video is not None:
        thumb = read_video_thumbnail(video)
        if thumb:
            return thumb

    audio = _first_media_file(directory, AUDIO_EXTS)
    if audio is not None:
        embedded = read_embedded_metadata(audio)
        if embedded.get("image"):
            return embedded["image"]

    return ""


def _collection_kind(audio_count: int, video_count: int) -> tuple[MediaKind, str, int]:
    if audio_count == 0 and video_count == 0:
        return MediaKind.FOLDER, "Playlist trống", 0
    if video_count > 0 and audio_count == 0:
        return MediaKind.VIDEO_PLAYLIST, f"{video_count} video", video_count
    if audio_count > 0 and video_count == 0:
        return MediaKind.ALBUM, f"{audio_count} bài", audio_count
    if audio_count >= video_count:
        return MediaKind.ALBUM, f"{audio_count} bài · {video_count} video", audio_count + video_count
    return MediaKind.VIDEO_PLAYLIST, f"{video_count} video · {audio_count} bài", audio_count + video_count


def scan_library_folder(folder: Path) -> list[MediaInfo]:
    """Scan one directory level: subfolders as collections + root files."""
    if not folder.exists():
        return []

    child_audio_counts: dict[str, int] = {}
    child_video_counts: dict[str, int] = {}
    for entry in folder.rglob("*"):
        if not entry.is_file():
            continue
        ext = entry.suffix.lower()
        if ext not in AUDIO_EXTS and ext not in VIDEO_EXTS:
            continue
        try:
            relative = entry.relative_to(folder)
        except ValueError:
            continue
        if not relative.parts:
            continue
        child_name = relative.parts[0]
        if ext in AUDIO_EXTS:
            child_audio_counts[child_name] = child_audio_counts.get(child_name, 0) + 1
        else:
            child_video_counts[child_name] = child_video_counts.get(child_name, 0) + 1

    items: list[MediaInfo] = []

    for child in sorted(folder.iterdir()):
        if child.name.startswith("."):
            continue
        if child.is_dir():
            audio_count = child_audio_counts.get(child.name, 0)
            video_count = child_video_counts.get(child.name, 0)
            kind, subtitle, child_count = _collection_kind(audio_count, video_count)

            display = resolve_display(
                str(child.resolve()),
                default_title=child.name,
                default_image=find_folder_preview_image(child),
            )
            preview_images = find_folder_track_thumbnails(child, 4)
            folder_image = display["image"] or find_folder_preview_image(child)
            if not preview_images and folder_image:
                preview_images = [folder_image]

            artist = str(display.get("artist") or "").strip()
            if artist.lower() in {"", "unknown artist", "video", "unknown", "music"}:
                artist = ""

            items.append(
                MediaInfo(
                    path=str(child.resolve()),
                    title=display["title"],
                    artist=artist,
                    subtitle=subtitle,
                    image=folder_image,
                    kind=kind,
                    child_count=child_count,
                    preview_images=preview_images,
                )
            )
            continue

        if child.is_file():
            ext = child.suffix.lower()
            if ext in AUDIO_EXTS or ext in VIDEO_EXTS:
                items.append(_media_from_file(child, audio_only=ext in AUDIO_EXTS))

    items = apply_order(items, folder, key=lambda item: Path(item.path).name)

    for i, item in enumerate(items, start=1):
        item.num = str(i)

    return items
