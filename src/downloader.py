import asyncio
import sys
from pathlib import Path
import yt_dlp

VALID_QUALITIES = {"480", "720", "1080", "1440", "2160", "best"}


class DownloadFailed(Exception):
    """Custom exception để lớp gọi (qml_backend.py) bắt an toàn, không lộ traceback của yt-dlp."""
    pass


class Downloader:
    def __init__(self, music_dir: Path, video_dir: Path):
        self.music_dir = music_dir
        self.video_dir = video_dir

    def _base_opts(self, out_dir: Path, progress_hook):
        return {
            "outtmpl": str(out_dir / "%(title)s.%(ext)s"),
            "progress_hooks": [progress_hook],
            "noplaylist": True,
            "quiet": True,
        }

    async def search(self, query: str, limit: int = 8):
        opts = {"quiet": True, "extract_flat": True, "default_search": f"ytsearch{limit}"}
        loop = asyncio.get_running_loop()  # fix #4

        def blocking_search():
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(query, download=False)
                    return info.get("entries", [])
            except Exception as e:
                raise DownloadFailed(str(e)) from e

        return await loop.run_in_executor(None, blocking_search)

    async def download_audio(self, url: str, progress_hook):
        opts = self._base_opts(self.music_dir, progress_hook)
        opts.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "320",
            }],
        })
        return await self._run(opts, url)

    async def download_video(self, url: str, progress_hook, quality: str = "1080"):
        if quality not in VALID_QUALITIES:  # fix #5
            quality = "1080"
        opts = self._base_opts(self.video_dir, progress_hook)
        if quality == "best":
            opts.update({"format": "bestvideo+bestaudio/best"})
        else:
            opts.update({"format": f"bestvideo[height<={quality}]+bestaudio/best"})
        return await self._run(opts, url)

    async def _run(self, opts, url):
        loop = asyncio.get_running_loop()  # fix #4

        def blocking_download():  # fix #7 - đổi tên tránh trùng
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.download([url])
            except Exception as e:  # fix #3
                raise DownloadFailed(str(e)) from e

        await loop.run_in_executor(None, blocking_download)
