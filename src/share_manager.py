"""Media share API client and local cache for Liminal."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from src.device_store import get_device_id
from src.downloader import extract_youtube_id
from src.settings_store import CONFIG_DIR

logger = logging.getLogger(__name__)

SHARE_API_BASE = "https://hoangminhduong.top"
_USER_AGENT = "Liminal/1.0"
_FETCH_TIMEOUT = 30
_THUMB_TIMEOUT = 15

SHARED_ITEMS_FILE = CONFIG_DIR / "shared_items.json"
SHARED_THUMB_DIR = Path(
    __import__("os").environ.get("XDG_CACHE_HOME", Path.home() / ".cache")
) / "liminal" / "shared"


def _api_url(path: str) -> str:
    base = SHARE_API_BASE.rstrip("/")
    suffix = path if path.startswith("/") else f"/{path}"
    return f"{base}{suffix}"


def _read_local_file() -> dict:
    if not SHARED_ITEMS_FILE.exists():
        return {}
    try:
        data = json.loads(SHARED_ITEMS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not read shared items cache: %s", exc)
        return {}
    return data if isinstance(data, dict) else {}


def _write_local_file(payload: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    SHARED_ITEMS_FILE.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def get_cached_items() -> list[dict]:
    data = _read_local_file()
    items = data.get("items")
    if not isinstance(items, list):
        return []
    return [dict(item) for item in items if isinstance(item, dict)]


def _request_json(
    method: str,
    path: str,
    *,
    body: dict | None = None,
) -> object:
    url = _api_url(path)
    data = None
    headers = {
        "User-Agent": _USER_AGENT,
        "Accept": "application/json",
    }
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=_FETCH_TIMEOUT) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        raw = response.read().decode(charset, errors="replace")
    return json.loads(raw)


def _guess_thumb_extension(content_type: str, url: str) -> str:
    lowered = (content_type or "").lower()
    if "png" in lowered:
        return ".png"
    if "webp" in lowered:
        return ".webp"
    if "gif" in lowered:
        return ".gif"
    path = urlparse(url).path.lower()
    for ext in (".png", ".webp", ".gif", ".jpeg", ".jpg"):
        if path.endswith(ext):
            return ext if ext != ".jpeg" else ".jpg"
    return ".jpg"


def _download_thumbnail(url: str, item_id: str) -> str:
    if not url:
        return ""
    SHARED_THUMB_DIR.mkdir(parents=True, exist_ok=True)
    safe_id = hashlib.sha256(item_id.encode("utf-8")).hexdigest()[:16]
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(request, timeout=_THUMB_TIMEOUT) as response:
        data = response.read()
        ext = _guess_thumb_extension(response.headers.get("Content-Type", ""), url)
        target = SHARED_THUMB_DIR / f"{safe_id}{ext}"
        target.write_bytes(data)
        return str(target.resolve())


def _normalize_item(raw: dict) -> dict | None:
    if not isinstance(raw, dict):
        return None
    share_id = str(raw.get("id") or "").strip()
    source_url = str(raw.get("source_url") or "").strip()
    title = str(raw.get("title") or "").strip()
    if not share_id or not source_url or not title:
        return None

    video_id = extract_youtube_id(source_url) or extract_youtube_id(share_id) or share_id
    media_type = str(raw.get("media_type") or "video").strip().lower()
    if media_type not in {"music", "video"}:
        media_type = "video"

    return {
        "id": share_id,
        "code": str(raw.get("code") or "").strip(),
        "title": title,
        "author": str(raw.get("author") or "").strip(),
        "thumbnail_url": str(raw.get("thumbnail_url") or "").strip(),
        "thumbnail_path": str(raw.get("thumbnail_path") or "").strip(),
        "source_url": source_url,
        "url": source_url,
        "media_type": media_type,
        "video_id": video_id,
        "redeemed_at": raw.get("redeemed_at"),
        "download_percent": float(raw.get("download_percent") or 0.0),
        "download_status": str(raw.get("download_status") or "pending"),
        "is_downloading": bool(raw.get("is_downloading")),
    }


async def _cache_thumbnails(items: list[dict]) -> list[dict]:
    loop = asyncio.get_running_loop()
    cached: list[dict] = []
    for item in items:
        row = dict(item)
        thumb_url = row.get("thumbnail_url") or ""
        if thumb_url and not row.get("thumbnail_path"):
            try:
                row["thumbnail_path"] = await loop.run_in_executor(
                    None,
                    _download_thumbnail,
                    thumb_url,
                    row["id"],
                )
            except Exception as exc:
                logger.warning("Shared thumbnail download failed for %r: %s", row.get("id"), exc)
                row["thumbnail_path"] = ""
        cached.append(row)
    return cached


def _merge_items(remote: list[dict], local: list[dict]) -> list[dict]:
    by_id: dict[str, dict] = {}
    for item in local:
        normalized = _normalize_item(item)
        if normalized:
            by_id[normalized["id"]] = normalized
    for item in remote:
        normalized = _normalize_item(item)
        if not normalized:
            continue
        prev = by_id.get(normalized["id"], {})
        merged = {**prev, **normalized}
        by_id[normalized["id"]] = merged
    return list(by_id.values())


async def refresh_shared_items() -> list[dict]:
    """Fetch redeemed shares for this device and refresh local cache."""
    device_id = get_device_id()
    loop = asyncio.get_running_loop()
    local = get_cached_items()

    try:
        payload = await loop.run_in_executor(
            None,
            lambda: _request_json(
                "GET",
                f"/api/media-share/mine?deviceId={urllib.parse.quote(device_id)}",
            ),
        )
    except urllib.error.HTTPError as exc:
        raise ValueError(f"Không thể tải danh sách chia sẻ (HTTP {exc.code}).") from exc
    except urllib.error.URLError as exc:
        raise ValueError("Không thể kết nối máy chủ chia sẻ. Kiểm tra mạng.") from exc
    except json.JSONDecodeError as exc:
        raise ValueError("Phản hồi máy chủ không hợp lệ.") from exc
    except TimeoutError as exc:
        raise ValueError("Tải danh sách chia sẻ quá thời gian chờ.") from exc

    remote_rows: list[dict] = []
    if isinstance(payload, dict):
        items = payload.get("items")
        if isinstance(items, list):
            remote_rows = [dict(row) for row in items if isinstance(row, dict)]

    merged = _merge_items(remote_rows, local)
    merged.sort(key=lambda row: str(row.get("redeemed_at") or ""), reverse=True)
    cached = await _cache_thumbnails(merged)
    _write_local_file({
        "device_id": device_id,
        "fetched_at": time.time(),
        "items": cached,
    })
    return cached


async def redeem_share_code(code: str) -> dict:
    device_id = get_device_id()
    normalized = code.replace(" ", "").replace("-", "").upper()
    loop = asyncio.get_running_loop()

    try:
        payload = await loop.run_in_executor(
            None,
            lambda: _request_json(
                "POST",
                "/api/media-share/redeem",
                body={"deviceId": device_id, "code": normalized},
            ),
        )
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise ValueError("Mã chia sẻ không tồn tại.") from exc
        raise ValueError(f"Không thể nhập mã (HTTP {exc.code}).") from exc
    except urllib.error.URLError as exc:
        raise ValueError("Không thể kết nối máy chủ chia sẻ.") from exc
    except json.JSONDecodeError as exc:
        raise ValueError("Phản hồi máy chủ không hợp lệ.") from exc

    if not isinstance(payload, dict):
        raise ValueError("Phản hồi máy chủ không hợp lệ.")

    item = _normalize_item(payload)
    if item is None:
        raise ValueError("Mã chia sẻ không hợp lệ.")

    items = _merge_items([item], get_cached_items())
    items.sort(key=lambda row: str(row.get("redeemed_at") or ""), reverse=True)
    cached = await _cache_thumbnails(items)
    _write_local_file({
        "device_id": device_id,
        "fetched_at": time.time(),
        "items": cached,
    })
    return item


async def create_share(
    *,
    title: str,
    author: str,
    source_url: str,
    thumbnail_url: str = "",
    media_type: str = "video",
) -> dict:
    device_id = get_device_id()
    loop = asyncio.get_running_loop()

    try:
        payload = await loop.run_in_executor(
            None,
            lambda: _request_json(
                "POST",
                "/api/media-share",
                body={
                    "deviceId": device_id,
                    "title": title.strip(),
                    "author": author.strip(),
                    "thumbnailUrl": thumbnail_url.strip(),
                    "sourceUrl": source_url.strip(),
                    "mediaType": media_type,
                },
            ),
        )
    except urllib.error.HTTPError as exc:
        raise ValueError(f"Không thể tạo mã chia sẻ (HTTP {exc.code}).") from exc
    except urllib.error.URLError as exc:
        raise ValueError("Không thể kết nối máy chủ chia sẻ.") from exc
    except json.JSONDecodeError as exc:
        raise ValueError("Phản hồi máy chủ không hợp lệ.") from exc

    if not isinstance(payload, dict):
        raise ValueError("Phản hồi máy chủ không hợp lệ.")

    code = str(payload.get("code") or "").strip()
    if not code:
        raise ValueError("Máy chủ không trả về mã chia sẻ.")

    return {"code": code, "id": str(payload.get("id") or "")}
