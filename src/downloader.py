"""Asynchronous yt-dlp service used by the QML backend."""

from __future__ import annotations

import asyncio
import re
import shutil
import threading
import logging
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qs, urlparse

logger = logging.getLogger(__name__)

try:
    import yt_dlp
except ImportError:  # Keep the application launchable without the optional downloader.
    yt_dlp = None

from src.google_drive import (
    GoogleDriveError,
    download_google_drive_file,
    is_google_drive_folder,
    is_google_drive_url,
    resolve_google_drive_link,
)


class DownloadFailed(Exception):
    """A user-facing yt-dlp failure without leaking its traceback to QML."""


class Download403Failed(DownloadFailed):
    """HTTP 403 during download — may be retried after the rest of a batch."""


class DownloadCancelled(DownloadFailed):
    """Download was cancelled by the user."""


PLAYLIST_RESOLVE_LIMIT = 50
_INVALID_FOLDER_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_YOUTUBE_ID_RE = re.compile(
    r"(?:youtube\.com/(?:watch\?(?:[^&\s]+&)*v=|embed/|shorts/|live/)|youtu\.be/(?:shorts/)?)"
    r"([A-Za-z0-9_-]{11})"
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


def resolve_cookie_options(
    cookies_browser: str = "",
    cookiefile_path: Path | None = None,
) -> dict:
    """Resolve yt-dlp cookie options with a priority fallback strategy.

    1. Try ``cookiesfrombrowser`` with the user-configured browser.
       Catches *all* exceptions (missing secretstorage, locked DB, etc.).
    2. Fall back to ``cookiefile`` if a pre-exported cookie file exists.
    3. Return an empty dict (anonymous) with a clear warning otherwise.

    Returns a dict safe to ``opts.update()`` directly into ydl_opts.
    """
    if not cookies_browser:
        logger.info("resolve_cookie_options: no browser configured, "
                     "trying cookiefile fallback")
    else:
        try:
            yt_dlp.cookies.extract_cookies_from_browser(cookies_browser)
        except Exception:
            logger.info(
                "resolve_cookie_options: cookiesfrombrowser('%s') unavailable — "
                "browser may be locked, secretstorage missing, or permission denied. "
                "Falling back to cookiefile.",
                cookies_browser,
            )
        else:
            logger.info(
                "resolve_cookie_options: using cookiesfrombrowser('%s')",
                cookies_browser,
            )
            return {"cookiesfrombrowser": (cookies_browser,)}

    if cookiefile_path is None:
        cookiefile_path = Path.home() / ".config" / "liminal" / "cookies.txt"

    if cookiefile_path.is_file():
        logger.info(
            "resolve_cookie_options: using cookiefile='%s'",
            cookiefile_path,
        )
        return {"cookiefile": str(cookiefile_path)}

    logger.warning(
        "resolve_cookie_options: NO cookie source available — "
        "running anonymous. YouTube may block or rate-limit requests. "
        "Configure a browser in Settings or export cookies to %s",
        cookiefile_path,
    )
    return {}


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


def _normalize_video_quality(quality: str) -> str:
    """Accept legacy UI keys (1440/2160/best) and canonical labels (2K/4K/Max)."""
    aliases = {
        "1440": "2K",
        "2160": "4K",
        "best": "Max",
    }
    return aliases.get(quality.strip(), quality.strip())


def _video_format_for_quality(quality: str) -> str:
    """Map the user-facing quality label to a yt-dlp format string.

    Do not restrict to mp4: YouTube's highest streams are often VP9/AV1 in
    webm/mkv.  yt-dlp merges them with ffmpeg without re-encoding.
    """
    quality = _normalize_video_quality(quality)
    mapping = {
        "480": "bestvideo[height<=480]+bestaudio/best[height<=480]/best",
        "720": "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
        "1080": "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
        "2K": "bestvideo[height<=1440]+bestaudio/best[height<=1440]/best",
        "4K": "bestvideo[height<=2160]+bestaudio/best[height<=2160]/best",
        "Max": "bestvideo*+bestaudio/best",
    }
    return mapping.get(quality, mapping["1080"])


# Progressive format fallback tiers ordered highest → lowest quality.
# Tier 0: best video+audio mp4 streams with container-agnostic fallback.
# Tier 1: 1080p combined file (single-stream, no merge needed).
# Tier 2: audio-only — matches original behaviour from commit 7651c65.
FORMAT_TIERS: list[str] = [
    "bv*[ext=mp4]+ba[ext=m4a]/bv*+ba/best[ext=mp4]/best",
    "best[height<=1080]",
    "bestaudio/best",
]

_VIDEO_YTDLP_OPTS: dict = {
    "merge_output_format": "mkv",
    "format_sort": [
        "res",
        "fps",
        "hdr:12",
        "codec:av01",
        "codec:av1",
        "codec:vp9.2",
        "codec:vp9",
        "codec:h265",
        "codec:h264",
        "size",
    ],
    "format_sort_force": True,
    "concurrent_fragment_downloads": 4,
    "retries": 10,
    "fragment_retries": 10,
    "writethumbnail": True,
    "writeinfojson": True,
    "writesubtitles": True,
    "writeautomaticsub": True,
    "subtitleslangs": ["vi"],
    "subtitlesformat": "best",
    "postprocessors": [
        {"key": "FFmpegMetadata"},
        {"key": "FFmpegThumbnailsConvertor", "format": "jpg"},
        {"key": "FFmpegSubtitlesConvertor", "format": "srt"},
    ],
}


def _resolved_download_path(prepared: Path, media_type: str) -> Path:
    if media_type == "music":
        mp3 = prepared.with_suffix(".mp3")
        return mp3 if mp3.exists() else prepared
    if prepared.exists():
        return prepared
    stem = prepared.with_suffix("")
    for ext in (".mkv", ".webm", ".mp4", ".m4v", ".mov"):
        candidate = stem.with_suffix(ext)
        if candidate.exists():
            return candidate
    return prepared


class Downloader:
    """Run the blocking yt-dlp Python API in executor worker threads."""

    def __init__(
        self,
        music_dir: Path,
        video_dir: Path,
        podcasts_dir: Path | None = None,
    ):
        self.music_dir = music_dir
        self.video_dir = video_dir
        self.podcasts_dir = podcasts_dir if podcasts_dir is not None else music_dir
        self._cancel_event = threading.Event()

    def cancel(self) -> None:
        """Signal all active downloads to abort."""
        self._cancel_event.set()

    def _reset_cancel(self) -> None:
        self._cancel_event.clear()

    def _check_cancelled(self) -> None:
        if self._cancel_event.is_set():
            raise DownloadCancelled("Tải xuống đã bị huỷ.")

    @staticmethod
    def availability_error(*, require_ffmpeg: bool = False) -> str | None:
        if yt_dlp is None:
            return "Chưa cài yt-dlp. Hãy chạy: pip install -r requirements.txt"
        if require_ffmpeg and shutil.which("ffmpeg") is None:
            return "Không tìm thấy ffmpeg. Cần cài ffmpeg để tải/ghi media."
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
                if is_google_drive_url(target) and not is_google_drive_folder(target):
                    return resolve_google_drive_link(target, media_type)
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
            except GoogleDriveError as exc:
                raise DownloadFailed(str(exc)) from exc
            except Exception as exc:
                raise DownloadFailed(f"Không thể đọc link: {exc}") from exc

        return await loop.run_in_executor(None, blocking_resolve)

    async def download(
        self,
        url_or_id: str,
        media_type: str,
        progress_hook: Callable[[dict], None],
        output_subdir: str | None = None,
        quality: str = "1080",
        cookies_browser: str = "",
        on_fallback: Callable[[str], None] | None = None,
    ) -> tuple[str, str]:
        error = self.availability_error(require_ffmpeg=media_type in {
            "music", "video", "podcast", "podcast_video",
        })
        if error:
            raise DownloadFailed(error)
        if media_type not in {"music", "video", "podcast", "podcast_video"}:
            raise DownloadFailed("Loại media không được hỗ trợ.")

        target = url_or_id.strip()
        if not target.startswith(("http://", "https://")):
            target = f"https://www.youtube.com/watch?v={target}"

        if media_type in {"podcast", "podcast_video"}:
            base_dir = self.podcasts_dir
        elif media_type == "music":
            base_dir = self.music_dir
        else:
            base_dir = self.video_dir

        subdir = _sanitize_folder_name(output_subdir) if output_subdir and output_subdir.strip() else ""
        output_dir = base_dir / subdir if subdir else base_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        
        def _clean_title_hook(info, *args, **kwargs):
            if info and info.get("title"):
                import re
                info["title"] = re.sub(r'[\\/*?:"<>|]', "-", info["title"])
            return None

        is_debug = logger.isEnabledFor(logging.DEBUG)
        opts = {
            "outtmpl": str(output_dir / "%(title)s.%(ext)s"),
            "progress_hooks": [progress_hook],
            "match_filter": _clean_title_hook,
            "noplaylist": True,
            "quiet": not is_debug,
            "no_warnings": not is_debug,
            "verbose": is_debug,
            "windowsfilenames": True,
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
            },
            "extractor_args": {
                "youtube": {
                    "player_client": ["ios", "android", "web"],
                },
            },
            "postprocessor_args": {
                "ffmpeg_i": ["-hwaccel", "none"],
            },
        }
        opts.update(resolve_cookie_options(cookies_browser))
        is_yt = "youtube.com" in target or "youtu.be" in target or "youtube" in target.lower()
        audio_like = (media_type == "music") or (media_type == "podcast" and not is_yt)
        if audio_like:
            opts["format"] = "bestaudio/best"
            opts.update({
                "writethumbnail": True,
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "0",
                    },
                    {"key": "FFmpegMetadata"},
                    {"key": "FFmpegThumbnailsConvertor", "format": "jpg"},
                    {"key": "EmbedThumbnail"},
                ],
            })
        else:
            opts.update(_VIDEO_YTDLP_OPTS)
            if media_type in {"podcast", "podcast_video"}:
                for key in ("writesubtitles", "writeautomaticsub", "subtitleslangs", "subtitlesformat"):
                    opts.pop(key, None)
                opts["postprocessors"] = [
                    p for p in opts.get("postprocessors", [])
                    if p.get("key") != "FFmpegSubtitlesConvertor"
                ]

        # Resolve final path: podcast_video uses same extensions as video.
        resolve_kind = "music" if audio_like else "video"

        self._reset_cancel()
        loop = asyncio.get_running_loop()

        def blocking_download() -> tuple[str, str]:
            def _do_download(dl_opts: dict) -> tuple[str, str]:
                with yt_dlp.YoutubeDL(dl_opts) as ydl:
                    info = ydl.extract_info(target, download=True)
                    video_id = str((info or {}).get("id") or url_or_id)
                    prepared = Path(ydl.prepare_filename(info))
                    final_path = _resolved_download_path(prepared, resolve_kind)
                    return video_id, str(final_path.resolve())

            if is_google_drive_url(target) and not is_google_drive_folder(target):
                return download_google_drive_file(
                    target,
                    output_dir,
                    "music" if audio_like else "video",
                    progress_hook,
                )

            # Only apply FORMAT_TIERS to YouTube video/podcast_video.
            # Audio-only and non-YouTube use a single format string as-is.
            try_tiers = not audio_like and is_yt
            tiers = FORMAT_TIERS if try_tiers else [opts.get("format", "best")]

            last_exc: Exception | None = None
            for idx, fmt_str in enumerate(tiers):
                if idx > 0:
                    logger.info(
                        "Falling back to FORMAT_TIERS[%d]='%s'",
                        idx, fmt_str,
                    )
                    if on_fallback is not None:
                        try:
                            on_fallback(fmt_str)
                        except Exception:
                            pass

                tier_opts = dict(opts)
                tier_opts["format"] = fmt_str

                try:
                    return _do_download(tier_opts)
                except GoogleDriveError:
                    raise
                except Exception as exc:
                    text = str(exc)

                    # Subtitle download failure → one retry without subtitles.
                    if "Unable to download video subtitles" in text:
                        try:
                            tier_opts_no_subs = dict(tier_opts)
                            tier_opts_no_subs["writesubtitles"] = False
                            tier_opts_no_subs["writeautomaticsub"] = False
                            return _do_download(tier_opts_no_subs)
                        except GoogleDriveError:
                            raise
                        except Exception as sub_exc:
                            sub_text = str(sub_exc)
                            if "403" in sub_text:
                                raise Download403Failed(f"Tải xuống thất bại: {sub_exc}") from sub_exc
                            if ("Requested format is not available" in sub_text
                                    or "Only images are available for download" in sub_text):
                                logger.info(
                                    "FORMAT_TIERS[%d]='%s' failed (subtitle retry too), trying next tier",
                                    idx, fmt_str,
                                )
                                last_exc = sub_exc
                                continue
                            raise DownloadFailed(f"Tải xuống thất bại: {sub_exc}") from sub_exc

                    # Format not available → advance to next tier.
                    if ("Requested format is not available" in text
                            or "Only images are available for download" in text):
                        logger.info(
                            "FORMAT_TIERS[%d]='%s' unavailable, trying next tier",
                            idx, fmt_str,
                        )
                        last_exc = exc
                        continue

                    # Non-retryable error — raise immediately.
                    if "403" in text:
                        raise Download403Failed(f"Tải xuống thất bại: {exc}") from exc
                    raise DownloadFailed(f"Tải xuống thất bại: {exc}") from exc

            # All tiers exhausted.
            raise DownloadFailed(
                "Không thể tải xuống với bất kỳ chất lượng nào. "
                "Hãy kiểm tra cookie trong Settings hoặc cập nhật yt-dlp lên bản mới nhất."
            ) from last_exc

        return await loop.run_in_executor(None, blocking_download)
