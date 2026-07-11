"""Asynchronous yt-dlp service used by the QML backend."""

from __future__ import annotations

import asyncio
import re
import shutil
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qs, urlparse

try:
    import yt_dlp
except ImportError:  # Keep the application launchable without the optional downloader.
    yt_dlp = None


class DownloadFailed(Exception):
    """A user-facing yt-dlp failure without leaking its traceback to QML."""


class Download403Failed(DownloadFailed):
    """HTTP 403 during download — may be retried after the rest of a batch."""


PLAYLIST_RESOLVE_LIMIT = 50
_INVALID_FOLDER_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_YOUTUBE_ID_RE = re.compile(
    r"(?:youtube\.com/(?:watch\?(?:[^&\s]+&)*v=|embed/|shorts/)|youtu\.be/)([A-Za-z0-9_-]{11})"
)


def extract_youtube_id(value: str) -> str:
    """Return an 11-char YouTube video id from a URL or bare id string."""
    text = (value or "").strip()
    if not text:
        return ""
    match = _YOUTUBE_ID_RE.search(text)
    if match:
        return match.group(1)
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", text):
        return text
    return ""


def _sanitize_folder_name(name: str) -> str:
    cleaned = _INVALID_FOLDER_CHARS.sub("", name.strip())
    cleaned = cleaned.rstrip(". ")
    if not cleaned:
        return "Playlist"
    return cleaned[:120]


def _duration_text(value: object) -> str:
    try:
        seconds = max(0, int(float(value or 0)))
    except (TypeError, ValueError):
        return "--:--"
    return f"{seconds // 60}:{seconds % 60:02d}" if seconds else "--:--"


def _thumbnail(info: dict) -> str:
    thumbnails = info.get("thumbnails") or []
    for entry in reversed(thumbnails):
        if isinstance(entry, dict) and entry.get("url"):
            return str(entry["url"])
    return str(info.get("thumbnail") or "")


def _is_video_result(item: dict) -> bool:
    """Reject channel/playlist entries returned by YouTube search."""
    if not item.get("id") or item.get("_type") not in (None, "url"):
        return False
    if item.get("ie_key") not in (None, "Youtube", "YoutubeTab"):
        return False
    url = str(item.get("webpage_url") or item.get("url") or "")
    lowered = url.lower()
    return not any(marker in lowered for marker in ("/channel/", "/playlist?", "list=", "/@"))


def _youtube_playlist_id(url: str) -> str | None:
    """Return the ``list`` query parameter from a YouTube URL, if present."""
    parsed = urlparse(url.strip())
    host = (parsed.hostname or "").lower().removeprefix("www.")
    if host == "youtu.be":
        playlist_id = (parse_qs(parsed.query).get("list") or [None])[0]
        return str(playlist_id) if playlist_id else None
    if "youtube" not in host:
        return None
    if parsed.path.rstrip("/") == "/playlist":
        playlist_id = (parse_qs(parsed.query).get("list") or [None])[0]
        return str(playlist_id) if playlist_id else None
    playlist_id = (parse_qs(parsed.query).get("list") or [None])[0]
    return str(playlist_id) if playlist_id else None


def _entry_to_result(item: dict, media_type: str) -> dict | None:
    if not item:
        return None
    video_id = str(item.get("id") or "")
    if not video_id:
        return None
    return {
        "id": video_id,
        "title": str(item.get("title") or "Không có tiêu đề"),
        "artist": str(item.get("uploader") or item.get("channel") or ""),
        "duration": _duration_text(item.get("duration")),
        "thumbnail_url": _thumbnail(item),
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "media_type": media_type,
    }


class Downloader:
    """Run the blocking yt-dlp Python API in executor worker threads."""

    def __init__(self, music_dir: Path, video_dir: Path):
        self.music_dir = music_dir
        self.video_dir = video_dir

    @staticmethod
    def availability_error(*, require_ffmpeg: bool = False) -> str | None:
        if yt_dlp is None:
            return "Chưa cài yt-dlp. Hãy chạy: pip install -r requirements.txt"
        if require_ffmpeg and shutil.which("ffmpeg") is None:
            return "Không tìm thấy ffmpeg. Cần cài ffmpeg để chuyển âm thanh sang MP3."
        return None

    async def search(self, query: str, media_type: str, limit: int = 10) -> list[dict]:
        error = self.availability_error()
        if error:
            raise DownloadFailed(error)
        limit = max(1, min(int(limit), 10))
        loop = asyncio.get_running_loop()

        def blocking_search() -> list[dict]:
            opts = {
                "quiet": True,
                "no_warnings": True,
                "extract_flat": True,
                "skip_download": True,
                "noplaylist": False,
            }
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    data = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
                    entries = list((data or {}).get("entries") or [])
                    results = []
                    for item in entries:
                        if not item:
                            continue
                        if not _is_video_result(item):
                            continue
                        if len(results) >= limit:
                            break
                        video_id = str(item.get("id") or "")
                        # Flat search is fast. Enrich only when fields needed by the UI
                        # are absent, and tolerate an individual metadata lookup failing.
                        if video_id and (not item.get("duration") or not _thumbnail(item)):
                            try:
                                full = ydl.extract_info(
                                    f"https://www.youtube.com/watch?v={video_id}",
                                    download=False,
                                )
                                if full:
                                    item = {**item, **full}
                            except Exception:
                                pass
                        results.append({
                            "id": video_id,
                            "title": str(item.get("title") or "Không có tiêu đề"),
                            "artist": str(item.get("uploader") or item.get("channel") or ""),
                            "duration": _duration_text(item.get("duration")),
                            "thumbnail_url": _thumbnail(item),
                            "url": str(item.get("webpage_url") or (
                                f"https://www.youtube.com/watch?v={video_id}" if video_id else ""
                            )),
                            "media_type": media_type,
                        })
                    return results
            except Exception as exc:
                raise DownloadFailed(f"Tìm kiếm YouTube thất bại: {exc}") from exc

        return await loop.run_in_executor(None, blocking_search)

    async def resolve_link(
        self,
        url: str,
        media_type: str,
        limit: int = PLAYLIST_RESOLVE_LIMIT,
    ) -> dict[str, object]:
        """Expand a pasted URL into downloadable entries (playlist or single video)."""
        error = self.availability_error()
        if error:
            raise DownloadFailed(error)
        target = url.strip()
        if not target.startswith(("http://", "https://")):
            target = f"https://www.youtube.com/watch?v={target}"
        limit = max(1, min(int(limit), PLAYLIST_RESOLVE_LIMIT))
        playlist_id = _youtube_playlist_id(target)
        loop = asyncio.get_running_loop()

        def blocking_resolve() -> dict[str, object]:
            try:
                if playlist_id:
                    opts = {
                        "quiet": True,
                        "no_warnings": True,
                        "extract_flat": "in_playlist",
                        "skip_download": True,
                        "playlistend": limit,
                    }
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        info = ydl.extract_info(target, download=False)
                    entries = list((info or {}).get("entries") or [])
                    results: list[dict] = []
                    for item in entries:
                        row = _entry_to_result(item, media_type)
                        if row:
                            results.append(row)
                        if len(results) >= limit:
                            break
                    if not results:
                        raise DownloadFailed("Playlist không có video nào để tải.")
                    folder = _sanitize_folder_name(
                        str((info or {}).get("title") or f"Playlist {playlist_id}")
                    )
                    return {"playlist_folder": folder, "items": results}

                with yt_dlp.YoutubeDL({
                    "quiet": True,
                    "no_warnings": True,
                    "skip_download": True,
                }) as ydl:
                    info = ydl.extract_info(target, download=False)
                row = _entry_to_result(info or {}, media_type)
                if not row:
                    raise DownloadFailed("Không thể đọc thông tin video từ link.")
                return {"playlist_folder": None, "items": [row]}
            except DownloadFailed:
                raise
            except Exception as exc:
                raise DownloadFailed(f"Không thể đọc link: {exc}") from exc

        return await loop.run_in_executor(None, blocking_resolve)

    async def download(
        self,
        url_or_id: str,
        media_type: str,
        progress_hook: Callable[[dict], None],
        output_subdir: str | None = None,
    ) -> tuple[str, str]:
        error = self.availability_error(require_ffmpeg=media_type == "music")
        if error:
            raise DownloadFailed(error)
        if media_type not in {"music", "video"}:
            raise DownloadFailed("Loại media không được hỗ trợ.")

        target = url_or_id.strip()
        if not target.startswith(("http://", "https://")):
            target = f"https://www.youtube.com/watch?v={target}"
        base_dir = self.music_dir if media_type == "music" else self.video_dir
        subdir = _sanitize_folder_name(output_subdir) if output_subdir and output_subdir.strip() else ""
        output_dir = base_dir / subdir if subdir else base_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        opts = {
            "outtmpl": str(output_dir / "%(title)s.%(ext)s"),
            "progress_hooks": [progress_hook],
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "format": "bestaudio/best" if media_type == "music" else "best[ext=mp4]/best",
        }
        if media_type == "music":
            opts.update({
                # EmbedThumbnail consumes the downloaded thumbnail file after
                # audio conversion; writethumbnail must therefore be enabled.
                "writethumbnail": True,
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "0",
                    },
                    {"key": "FFmpegMetadata"},
                    {"key": "EmbedThumbnail"},
                ],
            })
        else:
            opts.update({
                # Keep a JPEG sidecar next to the video. The library scanner
                # resolves this file by matching the video's stem.
                "writethumbnail": True,
                "postprocessors": [
                    {"key": "FFmpegMetadata"},
                    {"key": "FFmpegThumbnailsConvertor", "format": "jpg"},
                ],
            })

        loop = asyncio.get_running_loop()

        def blocking_download() -> tuple[str, str]:
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(target, download=True)
                    video_id = str((info or {}).get("id") or url_or_id)
                    prepared = Path(ydl.prepare_filename(info))
                    final_path = prepared.with_suffix(".mp3") if media_type == "music" else prepared
                    return video_id, str(final_path.resolve())
            except Exception as exc:
                text = str(exc)
                message = f"Tải xuống thất bại: {exc}"
                if "403" in text:
                    raise Download403Failed(message) from exc
                raise DownloadFailed(message) from exc

        return await loop.run_in_executor(None, blocking_download)
