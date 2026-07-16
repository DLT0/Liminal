"""Persistent user settings and media storage layout for Liminal."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

def _config_dir() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".config"
    return base / "liminal"


CONFIG_DIR = _config_dir()
SETTINGS_FILE = CONFIG_DIR / "settings.json"
SETTINGS_VERSION = 7

YOUTUBE_DEFAULTS: dict[str, str] = {
    "youtube_auth_mode": "oauth",
    "youtube_browser": "firefox",
    "youtube_browser_profile": "",
    "youtube_cookies_file": "",
}

OBSOLETE_SETTING_KEYS = (
    "discover_feed_url",
    "discover_feed_base_url",
    "discover_feed_slug",
    "discover_feed_api_key",
    "discover_cache_ttl_minutes",
    "discover_allowed_domains",
    "music_dir",
    "video_dir",
    "playlist_dir",
)

APP_DEFAULTS: dict = {
    "version": SETTINGS_VERSION,
    "download_quality": "1080",
    "video_playback_backend": "inapp",
    "auto_reload_enabled": True,
    "volume": 100,
    "muted": False,
    **YOUTUBE_DEFAULTS,
}

MUSIC_SUBDIR = "Music"
VIDEOS_SUBDIR = "Videos"
BOOKS_SUBDIR = "Books"
PODCASTS_SUBDIR = "Podcasts"

MEDIA_SUBDIRS = (MUSIC_SUBDIR, VIDEOS_SUBDIR, BOOKS_SUBDIR, PODCASTS_SUBDIR)


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
        "podcasts_dir": root / PODCASTS_SUBDIR,
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


def _read_settings_file() -> dict:
    if not SETTINGS_FILE.exists():
        return {}
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def read_settings_document_or_none() -> dict | None:
    """Return parsed settings, None when JSON is invalid (e.g. mid-save)."""
    if not SETTINGS_FILE.exists():
        return {}
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _strip_obsolete_settings(data: dict) -> dict:
    cleaned = dict(data)
    for key in OBSOLETE_SETTING_KEYS:
        cleaned.pop(key, None)
    return cleaned


def load_raw_settings() -> dict:
    """Load settings with app defaults; preserve user customization keys."""
    from src.state_store import migrate_state_from_settings

    migrate_state_from_settings()
    data = _strip_obsolete_settings(_read_settings_file())
    merged = dict(data)

    for key, default in APP_DEFAULTS.items():
        if key not in merged:
            merged[key] = default

    for key, default in YOUTUBE_DEFAULTS.items():
        value = merged.get(key, default)
        merged[key] = str(value) if value is not None else default

    merged["version"] = SETTINGS_VERSION
    return merged


def save_raw_settings(data: dict) -> None:
    """Persist settings while preserving user customization keys."""
    from src.state_store import SESSION_KEYS

    _ensure_config_dir()
    current = _strip_obsolete_settings(_read_settings_file())
    current.update(data)
    for key in SESSION_KEYS:
        current.pop(key, None)
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
        "books_dir": str(layout.get("books_dir", layout["media_root"] / BOOKS_SUBDIR)),
        "podcasts_dir": str(layout["podcasts_dir"]),
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


def get_podcasts_dir() -> Path:
    return Path(load_settings()["podcasts_dir"])
