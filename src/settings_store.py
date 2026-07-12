"""Persistent user settings and media storage layout for Liminal."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "liminal"
SETTINGS_FILE = CONFIG_DIR / "settings.json"
SETTINGS_VERSION = 4

YOUTUBE_DEFAULTS: dict[str, str] = {
    "youtube_auth_mode": "oauth",
    "youtube_browser": "firefox",
    "youtube_browser_profile": "",
    "youtube_cookies_file": "",
}

MUSIC_SUBDIR = "Music"
VIDEOS_SUBDIR = "Videos"
BOOKS_SUBDIR = "Books"

MEDIA_SUBDIRS = (MUSIC_SUBDIR, VIDEOS_SUBDIR, BOOKS_SUBDIR)


def _media_root_candidates(preferred: Path | None = None) -> list[Path]:
    """Return candidate roots in priority order (all outside OS system root)."""
    home = Path.home()
    candidates: list[Path] = []

    if preferred is not None:
        candidates.append(preferred.expanduser())

    if sys.platform == "win32":
        candidates.extend([
            home / "Media" / "Liminal",
            home / "Documents" / "Media" / "Liminal",
            home / "Videos" / "Liminal",
        ])
    else:
        candidates.extend([
            home / "Media" / "Liminal",
            home / "Documents" / "Media" / "Liminal",
        ])
        xdg_data = os.environ.get("XDG_DATA_HOME")
        if xdg_data:
            candidates.append(Path(xdg_data) / "liminal" / "media")
        candidates.append(home / ".local" / "share" / "liminal" / "media")

    # De-duplicate while preserving order
    seen: set[str] = set()
    unique: list[Path] = []
    for path in candidates:
        key = str(path.expanduser())
        if key not in seen:
            seen.add(key)
            unique.append(path.expanduser())
    return unique


def default_media_root() -> Path:
    """Preferred default storage location for the current platform."""
    return _media_root_candidates()[0]


def media_layout(root: Path) -> dict[str, Path]:
    """Return the canonical subfolder layout for *root*."""
    root = root.expanduser().resolve()
    return {
        "media_root": root,
        "music_dir": root / MUSIC_SUBDIR,
        "video_dir": root / VIDEOS_SUBDIR,
        "books_dir": root / BOOKS_SUBDIR,
    }


def ensure_media_layout(root: Path) -> dict[str, Path]:
    """Create *root* and all media subfolders, with writable fallbacks."""
    last_error: OSError | None = None
    for candidate in _media_root_candidates(root):
        try:
            layout = media_layout(candidate)
            layout["media_root"].mkdir(parents=True, exist_ok=True)
            for name in MEDIA_SUBDIRS:
                (layout["media_root"] / name).mkdir(parents=True, exist_ok=True)
            return layout
        except OSError as exc:
            last_error = exc
            continue
    if last_error is not None:
        raise last_error
    raise OSError("Could not create media storage directory")


def _ensure_config_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_raw_settings() -> dict:
    """Load the full settings document from disk."""
    if not SETTINGS_FILE.exists():
        return {"version": SETTINGS_VERSION, **YOUTUBE_DEFAULTS}
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            data = {}
    except (OSError, json.JSONDecodeError):
        data = {}
    merged = {
        "version": SETTINGS_VERSION,
        "theme_index": 0,
        "download_quality": "1080",
        "volume": 100,
        "muted": False,
        # ── Session / last-played restore ──────────────────────────────────
        "has_played_before":   False,
        "last_track_title":    "",
        "last_track_artist":   "",
        "last_track_thumbnail": "",
        "last_track_path":     "",
        "last_track_audio_only": True,
        "last_track_position":   0.0,
        # ──────────────────────────────────────────────────────────────────
        "show_visualizer":     True,
        **YOUTUBE_DEFAULTS,
    }
    merged.update({k: v for k, v in data.items() if k in merged or k == "media_root"})
    for key, default in YOUTUBE_DEFAULTS.items():
        value = data.get(key, default)
        merged[key] = str(value) if value is not None else default
    if isinstance(data.get("media_root"), str):
        merged["media_root"] = data["media_root"]
    return merged


def save_raw_settings(data: dict) -> None:
    """Persist the full settings document."""
    _ensure_config_dir()
    current = load_raw_settings()
    current.update(data)
    current["version"] = SETTINGS_VERSION
    SETTINGS_FILE.write_text(
        json.dumps(current, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _infer_media_root(paths: list[Path]) -> Path:
    if not paths:
        return default_media_root()
    resolved = [p.expanduser().resolve() for p in paths if str(p).strip()]
    if not resolved:
        return default_media_root()
    try:
        common = Path(os.path.commonpath([str(p) for p in resolved]))
    except ValueError:
        return resolved[0].parent
    if common in resolved:
        return common.parent
    return common


def _migrate_raw_settings(data: dict) -> str:
    """Convert legacy settings to a single media_root string."""
    media_root = data.get("media_root")
    if isinstance(media_root, str) and media_root.strip():
        return media_root.strip()

    legacy_keys = ("music_dir", "video_dir", "playlist_dir")
    legacy_paths = [
        Path(str(data[key]))
        for key in legacy_keys
        if isinstance(data.get(key), str) and str(data[key]).strip()
    ]
    if legacy_paths:
        return str(_infer_media_root(legacy_paths))

    return str(default_media_root())


def load_settings(*, create_if_missing: bool = True) -> dict[str, str]:
    """Load settings and ensure the on-disk media layout exists."""
    raw = load_raw_settings()
    if "media_root" not in raw or not str(raw.get("media_root", "")).strip():
        root = default_media_root()
        layout = ensure_media_layout(root)
        if create_if_missing:
            save_raw_settings({"media_root": str(layout["media_root"])})
        return _layout_to_settings(layout)

    root = Path(_migrate_raw_settings(raw))
    layout = ensure_media_layout(root)

    stored_root = raw.get("media_root")
    needs_save = (
        not isinstance(stored_root, str)
        or Path(stored_root).expanduser().resolve() != layout["media_root"]
        or raw.get("version") != SETTINGS_VERSION
        or any(key in raw for key in ("music_dir", "video_dir", "playlist_dir"))
    )
    if needs_save and create_if_missing:
        save_raw_settings({"media_root": str(layout["media_root"])})

    return _layout_to_settings(layout)


def _layout_to_settings(layout: dict[str, Path]) -> dict[str, str]:
    return {
        "media_root": str(layout["media_root"]),
        "music_dir": str(layout["music_dir"]),
        "video_dir": str(layout["video_dir"]),
    }


def save_settings(media_root: str) -> dict[str, str]:
    """Persist *media_root* and create the folder structure."""
    layout = ensure_media_layout(Path(media_root))
    save_raw_settings({"media_root": str(layout["media_root"])})
    return _layout_to_settings(layout)


def get_media_root() -> Path:
    return Path(load_settings()["media_root"])


def get_music_dir() -> Path:
    return Path(load_settings()["music_dir"])


def get_video_dir() -> Path:
    return Path(load_settings()["video_dir"])


def get_books_dir() -> Path:
    return Path(load_settings()["books_dir"])
