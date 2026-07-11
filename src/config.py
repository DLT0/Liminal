"""Centralized configuration for Liminal."""

from pathlib import Path


# --- Paths ---
ROOT = Path(__file__).resolve().parent.parent
CSS_DIR = ROOT / "src" / "css"

# --- Supported extensions ---
AUDIO_EXTS = {".mp3", ".flac", ".ogg", ".wav", ".m4a", ".opus", ".aac"}
VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v", ".ts", ".wmv"}

# --- MPV IPC ---
MPV_IPC_SOCKET = "/tmp/liminal-mpv.sock"

# --- YouTube Music / Browser auth ---
FLOORP_PROFILE = Path.home() / ".floorp" / "gkdz8bbm.PhuocLoc"
BROWSER_COOKIES = f"firefox:{FLOORP_PROFILE}" if FLOORP_PROFILE.exists() else None


def __getattr__(name: str):
    """Resolve media paths lazily from user settings."""
    if name == "MUSIC_DIR":
        from src.settings_store import get_music_dir

        return get_music_dir()
    if name == "VIDEO_DIR":
        from src.settings_store import get_video_dir

        return get_video_dir()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
