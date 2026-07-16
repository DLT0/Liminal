"""Scan media directories for supported files (recursive)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from src.config import AUDIO_EXTS, BOOK_EXTS, VIDEO_EXTS
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


def _iter_media_files(directory: Path, extensions: set[str]) -> list[Path]:
    """Collect media files under *directory* using os.scandir (faster than rglob on Linux)."""
    results: list[Path] = []
    if not directory.exists():
        return results

    stack = [directory]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    try:
                        path = Path(entry.path)
                        if path.is_dir():
                            if not entry.name.startswith("."):
                                stack.append(path)
                        elif path.is_file() and path.suffix.lower() in extensions:
                            results.append(path)
                    except OSError:
                        continue
        except OSError:
            continue
    return sorted(results, key=lambda path: str(path).lower())


def _child_media_counts(
    folder: Path,
) -> tuple[dict[str, int], dict[str, int]]:
    """Count audio/video files per top-level child folder in a single walk."""
    audio_counts: dict[str, int] = {}
    video_counts: dict[str, int] = {}
    for entry in _iter_media_files(folder, AUDIO_EXTS | VIDEO_EXTS):
        try:
            relative = entry.relative_to(folder)
        except ValueError:
            continue
        if not relative.parts:
            continue
        child_name = relative.parts[0]
        ext = entry.suffix.lower()
        if ext in AUDIO_EXTS:
            audio_counts[child_name] = audio_counts.get(child_name, 0) + 1
        elif ext in VIDEO_EXTS:
            video_counts[child_name] = video_counts.get(child_name, 0) + 1
    return audio_counts, video_counts


def _media_from_file(
    path: Path,
    *,
    audio_only: bool,
    fast: bool = False,
    include_cover: bool | None = None,
) -> MediaInfo:
    """Build MediaInfo for a single file.

    When *fast* is True, heavy cover extraction is skipped unless *include_cover*
    is explicitly True (used for root-level singles that paint immediately).
    """
    from src.metadata_store import find_cached_cover

    try:
        resolved = path.resolve()
    except OSError:
        resolved = path
    want_cover = (not fast) if include_cover is None else include_cover
    if audio_only:
        embedded = read_embedded_metadata(resolved, include_cover=want_cover)
        detected_image = embedded.get("image", "")
        if not detected_image:
            # Reuse previously extracted art without opening mutagen APIC again.
            detected_image = find_cached_cover(resolved)
    else:
        embedded = {}
        detected_image = read_video_thumbnail(resolved, extract=want_cover)
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
    *,
    fast: bool = False,
) -> list[MediaInfo]:
    """Recursively scan *directory* for media files with given extensions.

    When *fast* is True, skip ffmpeg frame extraction and embedded cover reads so
    the UI can populate immediately; thumbnails are filled in later on a worker thread.
    """
    if not directory.exists():
        return []

    files: list[MediaInfo] = []
    for media_path in _iter_media_files(directory, extensions):
        audio_only = media_path.suffix.lower() in AUDIO_EXTS
        files.append(_media_from_file(media_path, audio_only=audio_only, fast=fast))

    for i, media in enumerate(files, start=1):
        media.num = str(i)

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


def _first_media_file(directory: Path, extensions: set[str]) -> Path | None:
    for media_path in _iter_media_files(directory, extensions):
        return media_path
    return None


def _find_folder_track_thumbnails_fast(directory: Path, limit: int) -> list[str]:
    """Cheap collage sources: cover.jpg, video sidecars/cache, metadata overrides — no mutagen APIC."""
    from src.metadata_store import find_cached_cover, get_metadata

    images: list[str] = []
    seen: set[str] = set()

    def _add(img: str) -> bool:
        if not img or img in seen:
            return False
        seen.add(img)
        images.append(img)
        return len(images) >= limit

    cover = find_cover_image(directory)
    if cover and _add(cover):
        return images

    for media_path in _iter_media_files(directory, AUDIO_EXTS | VIDEO_EXTS):
        ext = media_path.suffix.lower()
        img = ""
        if ext in VIDEO_EXTS:
            img = read_video_thumbnail(media_path, extract=False)
        elif ext in AUDIO_EXTS:
            img = find_cached_cover(media_path)
            if not img:
                try:
                    resolved = str(media_path.resolve())
                except OSError:
                    resolved = str(media_path)
                meta_img = str(get_metadata(resolved).get("image") or "")
                if meta_img and Path(meta_img).is_file():
                    img = meta_img
        if img and _add(img):
            break

    return images


def find_folder_track_thumbnails(
    directory: Path,
    limit: int = 4,
    *,
    fast: bool = False,
) -> list[str]:
    """Return up to *limit* distinct cover/thumbnail paths from media inside *directory*."""
    if fast:
        return _find_folder_track_thumbnails_fast(directory, limit)

    images: list[str] = []
    seen: set[str] = set()

    for media_path in _iter_media_files(directory, AUDIO_EXTS | VIDEO_EXTS):
        ext = media_path.suffix.lower()
        img = ""
        if ext in AUDIO_EXTS:
            embedded = read_embedded_metadata(media_path, include_cover=True)
            display = resolve_display(
                str(media_path.resolve()),
                default_title=embedded.get("title") or media_path.stem,
                default_artist=embedded.get("artist") or "Music",
                default_image=embedded.get("image", ""),
            )
            img = display["image"]
        elif ext in VIDEO_EXTS:
            display = resolve_display(
                str(media_path.resolve()),
                default_title=media_path.stem,
                default_artist="Video",
                default_image=read_video_thumbnail(media_path, extract=True),
            )
            img = display["image"]

        if img and img not in seen:
            images.append(img)
            seen.add(img)
        if len(images) >= limit:
            break

    return images


def find_folder_preview_image(directory: Path, *, fast: bool = False) -> str:
    """Windows-style folder preview: cover art, else first video frame, else first audio cover."""
    cover = find_cover_image(directory)
    if cover:
        return cover

    video = _first_media_file(directory, VIDEO_EXTS)
    if video is not None:
        thumb = read_video_thumbnail(video, extract=not fast)
        if thumb:
            return thumb

    audio = _first_media_file(directory, AUDIO_EXTS)
    if audio is not None:
        embedded = read_embedded_metadata(audio, include_cover=not fast)
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


def scan_library_folder(folder: Path, *, fast: bool = False) -> list[MediaInfo]:
    """Scan one directory level: subfolders as collections + root files."""
    if not folder.exists():
        return []

    child_audio_counts, child_video_counts = _child_media_counts(folder)

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
                default_image=find_folder_preview_image(child, fast=fast),
            )
            preview_images = find_folder_track_thumbnails(child, 4, fast=fast)
            folder_image = display["image"] or find_folder_preview_image(child, fast=fast)
            if not preview_images and folder_image:
                preview_images = [folder_image]
            elif not folder_image and preview_images:
                folder_image = preview_images[0]

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
                # Root-level cards (singles / loose videos) are visible on first paint.
                # Load their covers even during a fast scan; nested tracks stay cheap.
                items.append(
                    _media_from_file(
                        child,
                        audio_only=ext in AUDIO_EXTS,
                        fast=fast,
                        include_cover=True,
                    )
                )
            elif ext in BOOK_EXTS:
                display = resolve_display(
                    str(child.resolve()),
                    default_title=child.stem,
                    default_artist="Sách",
                    default_image=find_folder_preview_image(child.parent),
                )
                items.append(
                    MediaInfo(
                        path=str(child.resolve()),
                        title=display["title"],
                        artist=display["artist"],
                        image=display["image"],
                        kind=MediaKind.FILE,
                    )
                )

    items = apply_order(items, folder, key=lambda item: Path(item.path).name)

    for i, item in enumerate(items, start=1):
        item.num = str(i)

    return items


def resolved_paths_in_child_folders(root: Path, extensions: set[str]) -> set[str]:
    """Resolved paths of media inside playlist/album subfolders under *root*.

    Symlinks count as their target file so root-level duplicates can be hidden
    from the singles grid when the same song is already in a playlist.
    """
    members: set[str] = set()
    if not root.exists():
        return members
    for child in root.iterdir():
        if not child.is_dir() or child.name.startswith("."):
            continue
        for media_path in _iter_media_files(child, extensions):
            try:
                members.add(str(media_path.resolve()))
            except OSError:
                members.add(str(media_path))
    return members


def scan_music_library_bundle(
    music_dir: Path,
    *,
    refresh: bool = False,
    cached_tracks: list[MediaInfo] | None = None,
    fast: bool = True,
) -> tuple[list[MediaInfo], list[MediaInfo]]:
    """Scan music root grid + all tracks in one executor-friendly call."""
    if not refresh and cached_tracks is not None:
        tracks = cached_tracks
    else:
        seen: set[str] = set()
        tracks = []
        for info in scan_directory(music_dir, AUDIO_EXTS, fast=fast):
            key = info.canonical_path or info.path
            if key in seen:
                continue
            seen.add(key)
            tracks.append(info)
        for i, track in enumerate(tracks, start=1):
            track.num = str(i)

    root_items = scan_library_folder(music_dir, fast=fast)
    return tracks, root_items


def scan_video_library_bundle(
    video_dir: Path,
    *,
    refresh: bool = False,
    cached_tracks: list[MediaInfo] | None = None,
    fast: bool = True,
) -> tuple[list[MediaInfo], list[MediaInfo]]:
    """Scan video root grid + all tracks in one executor-friendly call."""
    if not refresh and cached_tracks is not None:
        tracks = cached_tracks
    else:
        seen: set[str] = set()
        tracks = []
        for info in scan_directory(video_dir, VIDEO_EXTS, fast=fast):
            key = info.canonical_path or info.path
            if key in seen:
                continue
            seen.add(key)
            tracks.append(info)
        for i, track in enumerate(tracks, start=1):
            track.num = str(i)

    root_items = scan_library_folder(video_dir, fast=fast)
    return tracks, root_items
