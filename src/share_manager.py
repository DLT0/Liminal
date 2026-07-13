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

SHARE_API_BASE = "https://www.hoangminhduong.top"
_USER_AGENT = "Liminal/1.0"
_FETCH_TIMEOUT = 30
_AI_SORT_TIMEOUT = 45
_THUMB_TIMEOUT = 15
_MAX_REDIRECTS = 5
_SERIES_INITIAL_DOWNLOADS = 3
_PLAYLIST_INITIAL_DOWNLOADS = 3


def redeem_target_page(media_type: str) -> int:
    """Library page index for a redeemed share (2 = Music, 3 = Videos)."""
    kind = str(media_type or "video").strip().lower()
    if kind in {"music", "playlist"}:
        return 2
    return 3


def redeem_section_label(media_type: str) -> str:
    """Human-readable destination section for redeem success toasts."""
    kind = str(media_type or "video").strip().lower()
    if kind in {"music", "playlist"}:
        return "Music › Được chia sẻ với tôi"
    return "Videos › Được chia sẻ với tôi"


def redeem_success_message(item: dict) -> str:
    """Build a redeem success toast from the redeemed share row."""
    title = str(item.get("title") or "Nội dung").strip() or "Nội dung"
    media_type = str(item.get("media_type") or "video").strip().lower()
    section = redeem_section_label(media_type)
    message = f"«{title}» đã được thêm vào mục {section} của bạn."
    if media_type == "series":
        message += f" Tập 1–{_SERIES_INITIAL_DOWNLOADS} sẽ được tải tự động."
    elif media_type == "playlist":
        message += f" Bài 1–{_PLAYLIST_INITIAL_DOWNLOADS} sẽ được tải tự động."
    return message


SHARED_ITEMS_FILE = CONFIG_DIR / "shared_items.json"
SHARED_THUMB_DIR = Path(
    __import__("os").environ.get("XDG_CACHE_HOME", Path.home() / ".cache")
) / "liminal" / "shared"

_ALLOWED_SHARE_HOSTS = ("youtube.com", "youtu.be", "drive.google.com")


def is_allowed_share_url(url: str) -> bool:
    value = str(url or "").strip()
    if not value:
        return False
    try:
        host = (urlparse(value).hostname or "").lower().removeprefix("www.")
    except ValueError:
        return False
    return any(host == allowed or host.endswith(f".{allowed}") for allowed in _ALLOWED_SHARE_HOSTS)


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
    timeout: int = _FETCH_TIMEOUT,
) -> object:
    url = _api_url(path)
    payload = None
    headers = {
        "User-Agent": _USER_AGENT,
        "Accept": "application/json",
    }
    if body is not None:
        payload = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    current_method = method
    current_payload = payload

    for _ in range(_MAX_REDIRECTS):
        request = urllib.request.Request(
            url,
            data=current_payload,
            headers=headers,
            method=current_method,
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                raw = response.read().decode(charset, errors="replace")
            return json.loads(raw)
        except urllib.error.HTTPError as exc:
            if exc.code in (301, 302, 303, 307, 308):
                location = exc.headers.get("Location")
                if not location:
                    raise
                url = urllib.parse.urljoin(url, location)
                if exc.code in (301, 302, 303):
                    current_method = "GET"
                    current_payload = None
                continue
            raise
    raise ValueError("Quá nhiều lần chuyển hướng từ máy chủ chia sẻ.")


def _http_error_message(exc: urllib.error.HTTPError, *, series: bool = False) -> str:
    """Turn an HTTP error into a user-facing message."""
    detail = ""
    try:
        charset = exc.headers.get_content_charset() if exc.headers else None
        raw = exc.read().decode(charset or "utf-8", errors="replace")
        payload = json.loads(raw)
        if isinstance(payload, dict):
            detail = str(payload.get("error") or payload.get("message") or "").strip()
    except (OSError, json.JSONDecodeError, AttributeError, TypeError):
        detail = ""

    if detail == "mediaType không hợp lệ" and series:
        return (
            "Máy chủ chia sẻ chưa hỗ trợ phim bộ. "
            "Cần deploy bản mới của 2FA-SHARE-HMD lên hoangminhduong.top."
        )
    if detail == "mediaType không hợp lệ":
        return (
            "Máy chủ chia sẻ chưa hỗ trợ loại nội dung này. "
            "Cần deploy bản mới của 2FA-SHARE-HMD lên hoangminhduong.top."
        )
    if detail:
        return f"Không thể tạo mã chia sẻ: {detail}"
    return f"Không thể tạo mã chia sẻ (HTTP {exc.code})."


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


def _parse_episodes(raw: object) -> list[dict]:
    if raw is None:
        return []
    parsed = raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return []
    if not isinstance(parsed, list):
        return []
    episodes: list[dict] = []
    for index, entry in enumerate(parsed, start=1):
        if not isinstance(entry, dict):
            continue
        source_url = str(entry.get("source_url") or entry.get("sourceUrl") or "").strip()
        if not source_url:
            continue
        episode_index = int(entry.get("index") or index)
        title = str(entry.get("title") or f"Tập {episode_index}").strip()
        thumb = str(entry.get("thumbnail_url") or entry.get("thumbnailUrl") or "").strip()
        season = int(entry.get("season") or 1)
        episode_no = int(entry.get("episode") or episode_index)
        episodes.append({
            "index": episode_index,
            "season": season,
            "episode": episode_no,
            "title": title,
            "source_url": source_url,
            "thumbnail_url": thumb,
        })
    episodes.sort(key=lambda row: (
        int(row.get("season") or 1),
        int(row.get("episode") or row.get("index") or 0),
    ))
    return episodes


def _normalize_item(raw: dict) -> dict | None:
    if not isinstance(raw, dict):
        return None
    share_id = str(raw.get("id") or "").strip()
    title = str(raw.get("title") or "").strip()
    if not share_id or not title:
        return None

    media_type = str(raw.get("media_type") or "video").strip().lower()
    if media_type not in {"music", "video", "series", "playlist"}:
        media_type = "video"

    episodes = _parse_episodes(raw.get("episodes") or raw.get("episodes_json"))
    source_url = str(raw.get("source_url") or "").strip()
    if media_type in {"series", "playlist"}:
        if not episodes:
            return None
        if not source_url:
            source_url = str(episodes[0].get("source_url") or "").strip()
    elif not source_url:
        return None

    video_id = extract_youtube_id(source_url) or extract_youtube_id(share_id) or share_id

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
        "episodes": episodes,
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


def _remove_item_from_cache(share_id: str) -> list[dict]:
    """Drop one share from local cache by server id."""
    needle = (share_id or "").strip()
    if not needle:
        return get_cached_items()
    items = [item for item in get_cached_items() if str(item.get("id") or "") != needle]
    data = _read_local_file()
    _write_local_file({
        "device_id": data.get("device_id") or get_device_id(),
        "fetched_at": time.time(),
        "items": items,
    })
    return items


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
        if exc.code == 410:
            raise ValueError("Mã đã hết hạn (15 phút).") from exc
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
        raise ValueError(_http_error_message(exc)) from exc
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


async def create_series_share(
    *,
    title: str,
    author: str,
    thumbnail_url: str,
    episodes: list[dict],
) -> dict:
    if not episodes:
        raise ValueError("Phim bộ cần ít nhất một tập có link gốc.")
    device_id = get_device_id()
    loop = asyncio.get_running_loop()
    payload_episodes = [
        {
            "index": int(ep.get("index") or i + 1),
            "season": int(ep.get("season") or 1),
            "episode": int(ep.get("episode") or ep.get("index") or i + 1),
            "title": str(ep.get("title") or f"Tập {i + 1}").strip(),
            "sourceUrl": str(ep.get("source_url") or "").strip(),
            "thumbnailUrl": str(ep.get("thumbnail_url") or "").strip(),
        }
        for i, ep in enumerate(episodes)
        if is_allowed_share_url(str(ep.get("source_url") or ""))
    ]
    if not payload_episodes:
        raise ValueError("Không có tập nào có link gốc để chia sẻ.")

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
                    "sourceUrl": payload_episodes[0]["sourceUrl"],
                    "mediaType": "series",
                    "episodes": payload_episodes,
                },
            ),
        )
    except urllib.error.HTTPError as exc:
        raise ValueError(_http_error_message(exc, series=True)) from exc
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


async def create_playlist_share(
    *,
    title: str,
    author: str,
    thumbnail_url: str,
    tracks: list[dict],
) -> dict:
    if not tracks:
        raise ValueError("Playlist cần ít nhất một bài có link gốc.")
    device_id = get_device_id()
    loop = asyncio.get_running_loop()
    payload_tracks = [
        {
            "index": int(track.get("index") or i + 1),
            "season": 1,
            "episode": int(track.get("episode") or track.get("index") or i + 1),
            "title": str(track.get("title") or f"Bài {i + 1}").strip(),
            "sourceUrl": str(track.get("source_url") or "").strip(),
            "thumbnailUrl": str(track.get("thumbnail_url") or "").strip(),
        }
        for i, track in enumerate(tracks)
        if is_allowed_share_url(str(track.get("source_url") or ""))
    ]
    if not payload_tracks:
        raise ValueError("Không có bài nào có link gốc để chia sẻ.")

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
                    "sourceUrl": payload_tracks[0]["sourceUrl"],
                    "mediaType": "playlist",
                    "episodes": payload_tracks,
                },
            ),
        )
    except urllib.error.HTTPError as exc:
        raise ValueError(_http_error_message(exc, series=True)) from exc
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


def initial_series_download_episodes(episodes: list[dict], *, limit: int = _SERIES_INITIAL_DOWNLOADS) -> list[dict]:
    """Return the first N episodes to prefetch after redeeming a series share."""
    if not episodes:
        return []
    ordered = sorted(
        episodes,
        key=lambda ep: (
            int(ep.get("season") or 1),
            int(ep.get("episode") or ep.get("index") or 0),
        ),
    )
    return list(ordered[: max(1, limit)])


def initial_playlist_download_tracks(tracks: list[dict], *, limit: int = _PLAYLIST_INITIAL_DOWNLOADS) -> list[dict]:
    """Return the first N tracks to prefetch after redeeming a playlist share."""
    if not tracks:
        return []
    ordered = sorted(tracks, key=lambda track: int(track.get("index") or track.get("episode") or 0))
    return list(ordered[: max(1, limit)])


async def ai_sort_series_episodes(
    *,
    series_title: str,
    rows: list[dict],
) -> list[dict]:
    """Ask the share server (OpenAI proxy) to assign season/episode/order."""
    if not rows:
        return []

    from src.series_layout import apply_ai_sort_results, rows_to_ai_payload

    payload_rows = rows_to_ai_payload(rows)
    loop = asyncio.get_running_loop()

    try:
        response = await loop.run_in_executor(
            None,
            lambda: _request_json(
                "POST",
                "/api/series/sort",
                body={
                    "seriesTitle": series_title.strip() or "Phim bộ",
                    "episodes": payload_rows,
                },
                timeout=_AI_SORT_TIMEOUT,
            ),
        )
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            raw = exc.read().decode("utf-8", errors="replace")
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                detail = str(parsed.get("error") or "").strip()
        except Exception:
            detail = ""
        if exc.code == 429:
            raise ValueError("Quá nhiều yêu cầu AI. Thử lại sau.") from exc
        if exc.code in (502, 503):
            raise ValueError(detail or "Máy chủ AI chưa sẵn sàng.") from exc
        raise ValueError(detail or f"AI sắp xếp thất bại (HTTP {exc.code}).") from exc
    except urllib.error.URLError as exc:
        raise ValueError("Không thể kết nối máy chủ AI.") from exc
    except json.JSONDecodeError as exc:
        raise ValueError("Phản hồi AI không hợp lệ.") from exc
    except TimeoutError as exc:
        raise ValueError("AI sắp xếp quá thời gian chờ.") from exc

    if not isinstance(response, dict):
        raise ValueError("Phản hồi AI không hợp lệ.")

    ai_rows = response.get("episodes")
    if not isinstance(ai_rows, list):
        raise ValueError("Phản hồi AI thiếu danh sách tập.")

    return apply_ai_sort_results(rows, ai_rows)


async def dismiss_share(share_id: str) -> list[dict]:
    """Remove a redeemed share from server and local cache."""
    needle = (share_id or "").strip()
    if not needle:
        return get_cached_items()

    device_id = get_device_id()
    loop = asyncio.get_running_loop()

    try:
        await loop.run_in_executor(
            None,
            lambda: _request_json(
                "POST",
                "/api/media-share/dismiss",
                body={"deviceId": device_id, "shareId": needle},
            ),
        )
    except urllib.error.HTTPError as exc:
        if exc.code not in (404, 410):
            raise ValueError(f"Không thể xóa mục chia sẻ (HTTP {exc.code}).") from exc
    except urllib.error.URLError as exc:
        raise ValueError("Không thể kết nối máy chủ chia sẻ.") from exc
    except json.JSONDecodeError as exc:
        raise ValueError("Phản hồi máy chủ không hợp lệ.") from exc

    return _remove_item_from_cache(needle)
