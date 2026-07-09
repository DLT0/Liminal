"""YouTube Music search and download via yt-dlp."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import threading
import tempfile
from pathlib import Path
from typing import Callable, Optional

import yt_dlp

from src.config import BROWSER_COOKIES, MUSIC_DIR
from src.models import MediaInfo

logger = logging.getLogger(__name__)


# ── Cookies ─────────────────────────────────────────────────────

_COOKIES_FILE: str | None = None


def _init_cookies() -> None:
    """Extract browser cookies to a temp file once at app startup."""
    global _COOKIES_FILE
    if _COOKIES_FILE is not None or not BROWSER_COOKIES:
        return
    try:
        fd, path = tempfile.mkstemp(prefix="liminal_cookies_", suffix=".txt")
        os.close(fd)
        Path(path).write_text("# Netscape HTTP Cookie File\n")
        subprocess.run(
            [
                "yt-dlp",
                "--cookies-from-browser", BROWSER_COOKIES,
                "--cookies", path,
                "--batch-file", "/dev/null",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if Path(path).stat().st_size > 0:
            _COOKIES_FILE = path
            logger.info("Loaded %d cookies from %s", Path(path).stat().st_size, BROWSER_COOKIES)
        else:
            Path(path).unlink(missing_ok=True)
    except Exception as exc:
        logger.warning("Failed to extract cookies: %s", exc)


def _cookies_arg() -> list[str]:
    _init_cookies()
    return ["--cookies", _COOKIES_FILE] if _COOKIES_FILE else []


def _cookies_opt() -> dict:
    _init_cookies()
    return {"cookiefile": _COOKIES_FILE} if _COOKIES_FILE else {}


# ── Search ──────────────────────────────────────────────────────


def search_ytmusic(query: str, limit: int = 10) -> list[MediaInfo]:
    """Search YouTube Music, return results as ``MediaInfo`` list."""
    cmd = [
        "yt-dlp",
        *(_cookies_arg()),
        "--flat-playlist",
        "--dump-json",
        "--no-warnings",
        "--default-search", "ytsearch",
        f"ytsearch{limit}:{query}",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        return []
    except FileNotFoundError:
        logger.warning("yt-dlp not found — can't search")
        return []

    results: list[MediaInfo] = []
    for i, line in enumerate(result.stdout.strip().split("\n"), start=1):
        if not line:
            continue
        try:
            data = json.loads(line)
            dur = data.get("duration_string") or data.get("duration") or "--:--"
            if isinstance(dur, (int, float)):
                m, s = divmod(int(dur), 60)
                dur = f"{m}:{s:02d}"
            results.append(
                MediaInfo(
                    path=data.get("url", data.get("webpage_url", "")),
                    title=data.get("title", "Unknown"),
                    artist=data.get("uploader", data.get("channel", "Unknown Artist")),
                    duration=dur,
                    num=str(i),
                    url=data.get("url", data.get("webpage_url", "")),
                )
            )
        except json.JSONDecodeError:
            continue
    return results


# ── Download manager ────────────────────────────────────────────


class DownloadManager:
    """Manages concurrent downloads with progress tracking.

    Thread-safe: ``progress_of()`` can be called from any thread.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._progress: dict[str, dict] = {}  # track_id -> {percent, status}
        self._finished: dict[str, str] = {}  # track_id -> filepath or ""

    # ── public query helpers ──

    def progress_of(self, track_id: str) -> tuple[float, str]:
        with self._lock:
            p = self._progress.get(track_id)
            return (p["percent"], p["status"]) if p else (0.0, "")

    def is_downloading(self, track_id: str) -> bool:
        with self._lock:
            return track_id in self._progress and self._progress[track_id]["percent"] < 100

    def finish_status(self, track_id: str) -> str:
        with self._lock:
            return self._finished.get(track_id, "")

    # ── start download ──

    def download(
        self,
        url: str,
        track_id: str,
        on_done: Optional[Callable[[bool, Optional[str]], None]] = None,
    ) -> None:
        """Start downloading *url* in a daemon thread."""
        MUSIC_DIR.mkdir(parents=True, exist_ok=True)

        def _hook(d: dict) -> None:
            with self._lock:
                entry = self._progress.setdefault(track_id, {"percent": 0.0, "status": ""})
                if d["status"] == "downloading":
                    pct = d.get("_percent", 0)
                    if isinstance(pct, str):
                        try:
                            pct = float(pct.strip("%"))
                        except ValueError:
                            pct = 0.0
                    entry["percent"] = pct
                    entry["status"] = d.get("_speed_str", "") or ""
                elif d["status"] == "finished":
                    entry["percent"] = 100.0
                    entry["status"] = "Converting…"

        def _run() -> None:
            try:
                ydl_opts: dict = {
                    "format": "bestaudio/best",
                    "postprocessors": [
                        {
                            "key": "FFmpegExtractAudio",
                            "preferredcodec": "mp3",
                            "preferredquality": "192",
                        }
                    ],
                    "outtmpl": str(MUSIC_DIR / "%(title)s.%(ext)s"),
                    "progress_hooks": [_hook],
                    "quiet": True,
                    "no_warnings": True,
                }
                ydl_opts.update(_cookies_opt())

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])

                mp3s = sorted(
                    MUSIC_DIR.glob("*.mp3"),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )
                path = str(mp3s[0]) if mp3s else ""
                with self._lock:
                    self._finished[track_id] = path
                if on_done:
                    on_done(True, path)
            except Exception as exc:
                with self._lock:
                    self._finished[track_id] = ""
                    self._progress[track_id] = {"percent": 0.0, "status": f"Error: {exc}"}
                if on_done:
                    on_done(False, str(exc))

        threading.Thread(target=_run, daemon=True).start()
