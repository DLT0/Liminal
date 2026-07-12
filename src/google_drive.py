"""Google Drive helpers that avoid yt-dlp's rate-limited metadata API."""

from __future__ import annotations

import http.cookiejar
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable

_DRIVE_HOSTS = (
    "drive.google.com",
    "drive.usercontent.google.com",
    "docs.google.com",
)
_DRIVE_ID_RE = re.compile(
    r"(?:/file/d/|/d/|[?&]id=)([a-zA-Z0-9_-]{20,})"
)
_FILENAME_RE = re.compile(
    r"filename\*=UTF-8''([^;]+)|filename=\"?([^\";]+)\"?",
    re.IGNORECASE,
)
_CONFIRM_RE = re.compile(r"confirm=([0-9A-Za-z_-]+)")
_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
_REQUEST_HEADERS = {"User-Agent": _USER_AGENT}
_DOWNLOAD_BASES = (
    "https://drive.usercontent.google.com/download",
    "https://drive.google.com/uc",
    "https://docs.google.com/uc",
)
_RETRYABLE_CODES = {429, 500, 502, 503, 504}


class GoogleDriveError(Exception):
    """User-facing Google Drive failure."""


def is_google_drive_url(url: str) -> bool:
    value = (url or "").strip()
    if not value.startswith(("http://", "https://")):
        return False
    try:
        host = (urllib.parse.urlparse(value).hostname or "").lower().removeprefix("www.")
    except ValueError:
        return False
    return any(host == allowed or host.endswith(f".{allowed}") for allowed in _DRIVE_HOSTS)


def is_google_drive_folder(url: str) -> bool:
    lowered = (url or "").lower()
    return "/drive/folders/" in lowered or "/folders/" in lowered


def extract_drive_file_id(url: str) -> str:
    value = (url or "").strip()
    if not value:
        return ""
    match = _DRIVE_ID_RE.search(value)
    return match.group(1) if match else ""


def drive_download_url(file_id: str) -> str:
    query = urllib.parse.urlencode({"export": "download", "id": file_id})
    return f"https://drive.google.com/uc?{query}"


def format_drive_error(exc: Exception) -> str:
    text = str(exc)
    if "429" in text:
        return (
            "Google Drive tạm thời chặn do quá nhiều yêu cầu. "
            "Hãy thử lại sau vài phút hoặc mở link trên trình duyệt trước."
        )
    if "404" in text:
        return "Không tìm thấy file Google Drive. Kiểm tra link và quyền truy cập."
    if "403" in text:
        return "Không có quyền truy cập file Google Drive này."
    return f"Google Drive: {exc}"


def _filename_from_disposition(value: str) -> str:
    match = _FILENAME_RE.search(value or "")
    if not match:
        return ""
    raw = match.group(1) or match.group(2) or ""
    return urllib.parse.unquote(raw).strip()


def _safe_filename(name: str, *, file_id: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", (name or "").strip()).rstrip(". ")
    if cleaned:
        return cleaned[:180]
    return f"Google Drive {file_id[:8]}"


def _build_opener() -> tuple[urllib.request.OpenerDirector, http.cookiejar.CookieJar]:
    cookie_jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))
    return opener, cookie_jar


def _open_with_retries(
    opener: urllib.request.OpenerDirector,
    url: str,
    *,
    retries: int = 4,
) -> object:
    last_error: Exception | None = None
    for attempt in range(retries):
        request = urllib.request.Request(url, headers=_REQUEST_HEADERS)
        try:
            return opener.open(request, timeout=45)
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code not in _RETRYABLE_CODES or attempt >= retries - 1:
                raise GoogleDriveError(format_drive_error(exc)) from exc
            time.sleep(min(12, 2 ** attempt))
        except urllib.error.URLError as exc:
            last_error = exc
            if attempt >= retries - 1:
                raise GoogleDriveError("Không thể kết nối Google Drive.") from exc
            time.sleep(min(8, 2 ** attempt))
    raise GoogleDriveError(format_drive_error(last_error or RuntimeError("unknown drive error")))


def _confirm_url(cookie_jar: http.cookiejar.CookieJar, file_id: str, body: bytes) -> str | None:
    for item in cookie_jar:
        if item.name.startswith("download_warning"):
            query = urllib.parse.urlencode({
                "export": "download",
                "confirm": item.value,
                "id": file_id,
            })
            return f"{_DOWNLOAD_BASES[0]}?{query}"
    text = body.decode("utf-8", errors="replace")
    match = _CONFIRM_RE.search(text)
    if not match:
        return None
    query = urllib.parse.urlencode({
        "export": "download",
        "confirm": match.group(1),
        "id": file_id,
    })
    return f"{_DOWNLOAD_BASES[0]}?{query}"


def _is_binary_payload(content_type: str, disposition: str) -> bool:
    lowered = (content_type or "").lower()
    if "text/html" in lowered:
        return False
    if disposition and "attachment" in disposition.lower():
        return True
    return any(token in lowered for token in ("octet-stream", "video/", "audio/", "application/"))


def _probe_drive_file(file_id: str) -> tuple[str, int | None]:
    opener, cookie_jar = _build_opener()
    for base in _DOWNLOAD_BASES:
        query = urllib.parse.urlencode({"export": "download", "id": file_id})
        url = f"{base}?{query}"
        try:
            response = _open_with_retries(opener, url)
        except GoogleDriveError:
            continue

        disposition = response.headers.get("Content-Disposition", "")
        content_type = response.headers.get("Content-Type", "")
        content_length = response.headers.get("Content-Length")
        size = int(content_length) if content_length and content_length.isdigit() else None

        if _is_binary_payload(content_type, disposition):
            filename = _filename_from_disposition(disposition)
            response.close()
            return _safe_filename(filename, file_id=file_id), size

        body = response.read(65536)
        response.close()
        confirm_url = _confirm_url(cookie_jar, file_id, body)
        if not confirm_url:
            continue
        try:
            confirmed = _open_with_retries(opener, confirm_url)
        except GoogleDriveError:
            continue
        disposition = confirmed.headers.get("Content-Disposition", "")
        filename = _filename_from_disposition(disposition)
        content_length = confirmed.headers.get("Content-Length")
        size = int(content_length) if content_length and content_length.isdigit() else None
        confirmed.close()
        return _safe_filename(filename, file_id=file_id), size

    return f"Google Drive {file_id[:8]}", None


def resolve_google_drive_link(url: str, media_type: str) -> dict[str, object]:
    file_id = extract_drive_file_id(url)
    if not file_id:
        raise GoogleDriveError("Link Google Drive không hợp lệ.")
    title, _size = _probe_drive_file(file_id)
    return {
        "playlist_folder": None,
        "items": [{
            "id": file_id,
            "title": title,
            "artist": "",
            "duration": "--:--",
            "thumbnail_url": "",
            "url": drive_download_url(file_id),
            "media_type": media_type,
        }],
    }


def _emit_progress(
    progress_hook: Callable[[dict], None],
    *,
    file_id: str,
    downloaded: int,
    total: int | None,
    speed: float = 0.0,
) -> None:
    progress_hook({
        "status": "downloading",
        "downloaded_bytes": downloaded,
        "total_bytes": total,
        "total_bytes_estimate": total,
        "speed": speed,
        "info_dict": {"id": file_id},
    })


def _convert_to_mp3(source: Path) -> Path:
    if shutil.which("ffmpeg") is None:
        raise GoogleDriveError("Không tìm thấy ffmpeg để chuyển âm thanh sang MP3.")
    target = source.with_suffix(".mp3")
    result = subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(source), "-q:a", "0", str(target)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise GoogleDriveError(f"Chuyển MP3 thất bại: {detail or 'ffmpeg error'}")
    if source != target and source.exists():
        source.unlink(missing_ok=True)
    return target


def download_google_drive_file(
    url: str,
    output_dir: Path,
    media_type: str,
    progress_hook: Callable[[dict], None],
) -> tuple[str, str]:
    file_id = extract_drive_file_id(url)
    if not file_id:
        raise GoogleDriveError("Link Google Drive không hợp lệ.")

    opener, cookie_jar = _build_opener()
    response = None
    for base in _DOWNLOAD_BASES:
        query = urllib.parse.urlencode({"export": "download", "id": file_id})
        candidate = f"{base}?{query}"
        try:
            response = _open_with_retries(opener, candidate)
        except GoogleDriveError:
            continue

        disposition = response.headers.get("Content-Disposition", "")
        content_type = response.headers.get("Content-Type", "")
        if not _is_binary_payload(content_type, disposition):
            body = response.read(65536)
            response.close()
            confirm_url = _confirm_url(cookie_jar, file_id, body)
            if not confirm_url:
                response = None
                continue
            response = _open_with_retries(opener, confirm_url)
            disposition = response.headers.get("Content-Disposition", "")
        break

    if response is None:
        raise GoogleDriveError(
            "Không thể tải file Google Drive. Kiểm tra link, quyền truy cập, hoặc thử lại sau."
        )

    filename = _safe_filename(_filename_from_disposition(disposition), file_id=file_id)
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / filename
    if destination.exists():
        stem = destination.stem
        suffix = destination.suffix
        counter = 1
        while destination.exists():
            destination = output_dir / f"{stem} ({counter}){suffix}"
            counter += 1

    total_header = response.headers.get("Content-Length")
    total = int(total_header) if total_header and total_header.isdigit() else None
    downloaded = 0
    started = time.monotonic()
    last_emit = 0.0

    with destination.open("wb") as handle:
        while True:
            chunk = response.read(1024 * 256)
            if not chunk:
                break
            handle.write(chunk)
            downloaded += len(chunk)
            now = time.monotonic()
            if now - last_emit >= 0.25:
                elapsed = max(now - started, 0.001)
                _emit_progress(
                    progress_hook,
                    file_id=file_id,
                    downloaded=downloaded,
                    total=total,
                    speed=downloaded / elapsed,
                )
                last_emit = now

    response.close()
    _emit_progress(progress_hook, file_id=file_id, downloaded=downloaded, total=total or downloaded)

    final_path = destination
    if media_type == "music" and final_path.suffix.lower() != ".mp3":
        final_path = _convert_to_mp3(final_path)

    return file_id, str(final_path.resolve())
