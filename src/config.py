"""Centralized configuration for Liminal."""

import platform
from pathlib import Path


# --- Paths ---
ROOT = Path(__file__).resolve().parent.parent
CSS_DIR = ROOT / "src" / "css"

MUSIC_DIR = Path("/DATA/Media/Music/Liminal")
VIDEO_DIR = Path("/DATA/Media/Video/Liminal")

# --- Supported extensions ---
AUDIO_EXTS = {".mp3", ".flac", ".ogg", ".wav", ".m4a", ".opus", ".aac"}
VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v", ".ts", ".wmv"}

# --- MPV IPC ---
MPV_IPC_SOCKET = "/tmp/liminal-mpv.sock"

# --- YouTube Music / Browser auth ---
# yt-dlp cookies-from-browser argument, e.g. "firefox:~/.floorp/gkdz8bbm.PhuocLoc"
# Set to None to disable; set to a string to enable authenticated search/download.
# Floorp on Arch Linux default:
FLOORP_PROFILE = Path.home() / ".floorp" / "gkdz8bbm.PhuocLoc"
BROWSER_COOKIES = f"firefox:{FLOORP_PROFILE}" if FLOORP_PROFILE.exists() else None
