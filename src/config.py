"""Centralized configuration for Liminal."""

from pathlib import Path


# --- Paths ---
ROOT = Path(__file__).resolve().parent.parent
CSS_DIR = ROOT / "src" / "css"

# --- Supported extensions ---
AUDIO_EXTS = {".mp3", ".flac", ".ogg", ".wav", ".m4a", ".opus", ".aac"}
VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v", ".ts", ".wmv"}
BOOK_EXTS = {".pdf", ".epub", ".mobi", ".azw3", ".fb2", ".djvu", ".cbr", ".cbz"}

# --- MPV IPC ---
MPV_IPC_SOCKET = "/tmp/liminal-mpv.sock"

# Extra loudness for mpv/Qt players (0 = off). ~3 dB is a modest boost at max volume.
MPV_AUDIO_GAIN_DB = 0


def mpv_audio_gain_factor() -> float:
    """Linear gain multiplier for Qt Multimedia fallback."""
    if MPV_AUDIO_GAIN_DB <= 0:
        return 1.0
    return 10 ** (MPV_AUDIO_GAIN_DB / 20.0)


def mpv_audio_gain_args() -> tuple[str, ...]:
    if MPV_AUDIO_GAIN_DB <= 0:
        return ()
    return (f"--af=volume={MPV_AUDIO_GAIN_DB}dB",)

# --- YouTube Music / Browser auth ---
# Detect browser cookie sources in priority order for yt-dlp.
# User can override via youtube_cookies_file / youtube_browser_profile in settings.
_BROWSER_DIRS = {
    "firefox": [
        Path.home() / ".mozilla" / "firefox",
        Path.home() / ".librewolf",
        Path.home() / ".floorp",
        Path.home() / "snap" / "firefox" / "common" / ".mozilla" / "firefox",
    ],
    "chromium": [
        Path.home() / ".config" / "chromium",
        Path.home() / "snap" / "chromium" / "common" / "chromium",
    ],
    "chrome": [
        Path.home() / ".config" / "google-chrome",
    ],
    "brave": [
        Path.home() / ".config" / "BraveSoftware" / "Brave-Browser",
    ],
    "opera": [
        Path.home() / ".config" / "opera",
    ],
    "vivaldi": [
        Path.home() / ".config" / "vivaldi",
    ],
}


def _find_browser_profile(browser: str, browser_dirs: list[Path]) -> str | None:
    """Look for a profile directory inside *browser_dirs* with cookies.sqlite."""
    if browser in {"firefox"}:
        for base in browser_dirs:
            if not base.exists():
                continue
            try:
                for child in sorted(base.iterdir()):
                    profile = child
                    # Handle snap-style paths (profiles.ini → real path)
                    if child.name == "profiles.ini":
                        continue
                    if profile.is_dir() and (profile / "cookies.sqlite").exists():
                        return str(profile)
            except OSError:
                continue
        return None

    for base in browser_dirs:
        if base.exists() and (base / "Default" / "Cookies").exists():
            return str(base / "Default")
    return None


def _browser_cookies() -> str | None:
    """Auto-detect browser cookies for yt-dlp on Linux.

    Checks Firefox (including Librewolf, Floorp, snap), then Chromium-based
    browsers (Chrome, Brave, Opera, Vivaldi). Falls back to None if nothing
    is found.
    """
    for browser, dirs in _BROWSER_DIRS.items():
        profile = _find_browser_profile(browser, dirs)
        if profile:
            return f"{browser}:{profile}"
    return None


BROWSER_COOKIES = _browser_cookies()


def __getattr__(name: str):
    """Resolve media paths lazily from user settings."""
    if name == "MUSIC_DIR":
        from src.settings_store import get_music_dir

        return get_music_dir()
    if name == "VIDEO_DIR":
        from src.settings_store import get_video_dir

        return get_video_dir()
    if name == "BOOKS_DIR":
        from src.settings_store import get_books_dir

        return get_books_dir()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
