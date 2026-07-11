"""Asynchronous yt-dlp service used by the QML backend."""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from typing import Callable

try:
    import yt_dlp
except ImportError:  # Keep the application launchable without the optional downloader.
    yt_dlp = None


class DownloadFailed(Exception):
    """A user-facing yt-dlp failure without leaking its traceback to QML."""


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
                    entries = list((data or {}).get("entries") or [])[:limit]
                    results = []
                    for item in entries:
                        if not item:
                            continue
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

    async def download(
        self,
        url_or_id: str,
        media_type: str,
        progress_hook: Callable[[dict], None],
    ) -> tuple[str, str]:
        error = self.availability_error(require_ffmpeg=media_type == "music")
        if error:
            raise DownloadFailed(error)
        if media_type not in {"music", "video"}:
            raise DownloadFailed("Loại media không được hỗ trợ.")

        target = url_or_id.strip()
        if not target.startswith(("http://", "https://")):
            target = f"https://www.youtube.com/watch?v={target}"
        output_dir = self.music_dir if media_type == "music" else self.video_dir
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
                raise DownloadFailed(f"Tải xuống thất bại: {exc}") from exc

        return await loop.run_in_executor(None, blocking_download)
