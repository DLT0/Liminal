"""Per-media metadata overrides (title, artist, cover image)."""

from __future__ import annotations

import json
import hashlib
import os
import shutil
import subprocess
from pathlib import Path

from src.downloader import extract_youtube_id
from src.settings_store import CONFIG_DIR

METADATA_FILE = CONFIG_DIR / "metadata.json"
COVER_NAMES = ("cover.jpg", "cover.png", "folder.jpg", "folder.png", "album.jpg", "album.png")
COVER_CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "liminal" / "thumbnails"

try:
    from mutagen import File as MutagenFile
    from mutagen.id3 import APIC
except ImportError:  # The library remains scannable with filename fallbacks.
    MutagenFile = None
    APIC = None


def _ensure_config_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def _load_all() -> dict[str, dict]:
    if not METADATA_FILE.exists():
        return {}
    try:
        data = json.loads(METADATA_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_all(data: dict[str, dict]) -> None:
    _ensure_config_dir()
    METADATA_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def get_metadata(path: str) -> dict:
    """Return stored overrides for *path* (may be empty)."""
    return dict(_load_all().get(path, {}))


def set_metadata(path: str, **fields: str) -> dict:
    """Merge *fields* into metadata for *path* and persist."""
    all_data = _load_all()
    entry = dict(all_data.get(path, {}))
    for key, value in fields.items():
        if value is None:
            entry.pop(key, None)
        else:
            entry[key] = value
    if entry:
        all_data[path] = entry
    else:
        all_data.pop(path, None)
    _save_all(all_data)
    return entry


def delete_metadata(path: str) -> None:
    all_data = _load_all()
    if path in all_data:
        del all_data[path]
        _save_all(all_data)


def find_cover_image(directory: Path) -> str:
    """Return local cover image path for *directory* if one exists."""
    for name in COVER_NAMES:
        candidate = directory / name
        if candidate.is_file():
            return str(candidate.resolve())
    meta = get_metadata(str(directory.resolve()))
    image = meta.get("image", "")
    if image and Path(image).is_file():
        return image
    return ""


def _first_tag(tags, *names: str) -> str:
    """Read the first textual tag across ID3 and mutagen's easy mappings."""
    if not tags:
        return ""
    for name in names:
        value = tags.get(name)
        if value is None:
            continue
        text = getattr(value, "text", value)
        if isinstance(text, (list, tuple)):
            text = text[0] if text else ""
        if text:
            return str(text)
    return ""


def _cache_embedded_cover(path: Path, data: bytes, mime: str) -> str:
    """Persist embedded art to a stable cache URL consumable by QML Image."""
    stat = path.stat()
    cache_key = hashlib.sha256(
        f"{path.resolve()}:{stat.st_mtime_ns}:{stat.st_size}".encode()
    ).hexdigest()
    extension = ".png" if mime.lower() == "image/png" else ".jpg"
    target = COVER_CACHE_DIR / f"{cache_key}{extension}"
    if not target.exists():
        COVER_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return str(target.resolve())


def _cover_cache_path(path: Path, extension: str = ".jpg") -> Path:
    stat = path.stat()
    cache_key = hashlib.sha256(
        f"{path.resolve()}:{stat.st_mtime_ns}:{stat.st_size}".encode()
    ).hexdigest()
    return COVER_CACHE_DIR / f"{cache_key}{extension}"


def read_video_thumbnail(path: Path) -> str:
    """Find a yt-dlp sidecar, or cache a representative frame for old videos."""
    for extension in (".jpg", ".jpeg", ".png", ".webp"):
        candidate = path.with_suffix(extension)
        if candidate.is_file():
            return str(candidate.resolve())

    if shutil.which("ffmpeg") is None:
        return ""
    try:
        target = _cover_cache_path(path)
        if target.is_file():
            return str(target.resolve())
        COVER_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        # One second avoids the common all-black opening frame while keeping
        # first-time library scans reasonably quick.
        subprocess.run(
            [
                "ffmpeg", "-y", "-ss", "1", "-i", str(path),
                "-frames:v", "1", "-q:v", "3", str(target),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=15,
        )
        return str(target.resolve()) if target.is_file() else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def read_embedded_source_id(path: Path) -> str:
    """Read a YouTube video id from embedded tags (WOAS, comment, description)."""
    if MutagenFile is None:
        return ""
    try:
        audio = MutagenFile(path)
        tags = getattr(audio, "tags", None)
        if not tags:
            return ""
        for name in (
            "WOAS",
            "comment",
            "COMM::eng",
            "COMM",
            "TXXX:URL",
            "TXXX:WEBSITE",
            "TIT3",
            "description",
        ):
            text = _first_tag(tags, name)
            video_id = extract_youtube_id(text)
            if video_id:
                return video_id
        return ""
    except Exception:
        return ""


def resolve_source_id(path: str | Path, *, cache: bool = True) -> str:
    """Return the YouTube source id for a library file, persisting when discovered."""
    resolved = str(Path(path).resolve())
    meta = get_metadata(resolved)
    stored = str(meta.get("source_id") or "")
    if stored:
        return stored
    embedded = read_embedded_source_id(Path(resolved))
    if embedded and cache:
        set_metadata(resolved, source_id=embedded)
    return embedded


def resolve_source_url(path: str | Path, *, cache: bool = True) -> str:
    """Return the original download URL (YouTube/Drive) when available."""
    resolved = str(Path(path).resolve())
    meta = get_metadata(resolved)
    stored = str(meta.get("source_url") or "").strip()
    if stored:
        return stored

    source_id = resolve_source_id(resolved, cache=cache)
    video_id = extract_youtube_id(source_id)
    if video_id:
        return f"https://www.youtube.com/watch?v={video_id}"
    return ""


def read_embedded_metadata(path: Path) -> dict[str, str]:
    """Return title, artist and cached embedded cover from an audio file."""
    if MutagenFile is None:
        return {"title": "", "artist": "", "image": ""}
    try:
        audio = MutagenFile(path)
        tags = getattr(audio, "tags", None)
        title = _first_tag(tags, "TIT2", "title")
        artist = _first_tag(tags, "TPE1", "artist")
        image = ""
        if tags and APIC is not None:
            for tag in tags.values():
                if isinstance(tag, APIC) and tag.data:
                    image = _cache_embedded_cover(path, tag.data, tag.mime or "image/jpeg")
                    break
        return {"title": title, "artist": artist, "image": image}
    except Exception:
        # A corrupt/unsupported media file must not abort the whole library scan.
        return {"title": "", "artist": "", "image": ""}


def resolve_display(
    path: str,
    *,
    default_title: str,
    default_artist: str = "",
    default_image: str = "",
) -> dict[str, str]:
    """Merge filesystem defaults with stored metadata."""
    meta = get_metadata(path)
    return {
        "title": meta.get("title") or default_title,
        "artist": meta.get("artist") or default_artist or "Unknown Artist",
        "image": meta.get("image") or default_image or find_cover_image(
            Path(path).parent if Path(path).is_file() else Path(path)
        ),
    }


def set_cover_image(path: str, source_image: str) -> str:
    """Copy *source_image* next to the media file/folder as cover.jpg."""
    target_dir = Path(path)
    if target_dir.is_file():
        target_dir = target_dir.parent
    target_dir.mkdir(parents=True, exist_ok=True)
    dest = target_dir / "cover.jpg"
    shutil.copy2(source_image, dest)
    set_metadata(path, image=str(dest.resolve()))
    return str(dest.resolve())
