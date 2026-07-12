"""Discover feed fetch, validation, and local cache for Liminal."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from src.downloader import extract_youtube_id
from src.settings_store import CONFIG_DIR, DISCOVER_FEED_BASE_URL, load_raw_settings

logger = logging.getLogger(__name__)

_USER_AGENT = "Liminal/1.0"
_FETCH_TIMEOUT = 30
_THUMB_TIMEOUT = 15

DISCOVER_CACHE_FILE = CONFIG_DIR / "discover_cache.json"
DISCOVER_THUMB_DIR = Path(
    __import__("os").environ.get("XDG_CACHE_HOME", Path.home() / ".cache")
) / "liminal" / "discover"

REQUIRED_FIELDS = ("id", "title", "author", "thumbnail_url", "source_url")
DEFAULT_ALLOWED_DOMAINS = (
    "youtube.com",
    "youtu.be",
    "drive.google.com",
)
DEFAULT_CACHE_TTL_MINUTES = 30


def _discover_settings() -> dict:
    raw = load_raw_settings()
    domains = raw.get("discover_allowed_domains")
    if not isinstance(domains, list) or not domains:
        domains = list(DEFAULT_ALLOWED_DOMAINS)
    else:
        domains = [str(d).strip().lower() for d in domains if str(d).strip()]
        if not domains:
            domains = list(DEFAULT_ALLOWED_DOMAINS)

    ttl = raw.get("discover_cache_ttl_minutes", DEFAULT_CACHE_TTL_MINUTES)
    try:
        ttl_minutes = max(1, int(ttl))
    except (TypeError, ValueError):
        ttl_minutes = DEFAULT_CACHE_TTL_MINUTES

    feed_url = str(raw.get("discover_feed_url") or "").strip()
    feed_base = str(raw.get("discover_feed_base_url") or DISCOVER_FEED_BASE_URL).strip().rstrip("/")
    feed_slug = str(raw.get("discover_feed_slug") or "").strip()
    api_key = str(raw.get("discover_feed_api_key") or "").strip()
    return {
        "feed_url": feed_url,
        "feed_base_url": feed_base,
        "feed_slug": feed_slug,
        "feed_api_key": api_key,
        "cache_ttl_minutes": ttl_minutes,
        "allowed_domains": domains,
    }


def _resolve_feed_url(settings: dict) -> str:
    explicit = str(settings.get("feed_url") or "").strip()
    if explicit:
        return explicit
    slug = str(settings.get("feed_slug") or "").strip()
    base = str(settings.get("feed_base_url") or DISCOVER_FEED_BASE_URL).strip().rstrip("/")
    if slug:
        return f"{base}/api/discover/{slug}"
    return ""


def _normalize_host(host: str) -> str:
    value = (host or "").strip().lower()
    if value.startswith("www."):
        return value[4:]
    return value


def _domain_allowed(url: str, allowed_domains: list[str]) -> bool:
    try:
        host = _normalize_host(urlparse(url).netloc)
        if not host:
            return False
        for domain in allowed_domains:
            needle = _normalize_host(domain)
            if not needle:
                continue
            if host == needle or host.endswith("." + needle):
                return True
    except Exception:
        logger.warning("Could not parse URL for domain check: %r", url)
    return False


def _validate_item(raw: dict, allowed_domains: list[str]) -> dict | None:
    if not isinstance(raw, dict):
        return None

    missing = [field for field in REQUIRED_FIELDS if not str(raw.get(field) or "").strip()]
    if missing:
        logger.warning("Skipping discover item missing fields %s: %r", missing, raw)
        return None

    source_url = str(raw["source_url"]).strip()
    if not _domain_allowed(source_url, allowed_domains):
        logger.warning("Skipping discover item with disallowed domain: %r", source_url)
        return None

    media_type = str(raw.get("media_type") or "video").strip().lower()
    if media_type not in {"music", "video"}:
        media_type = "video"

    item_id = str(raw["id"]).strip()
    video_id = extract_youtube_id(source_url) or extract_youtube_id(item_id) or item_id

    return {
        "id": item_id,
        "title": str(raw["title"]).strip(),
        "author": str(raw["author"]).strip(),
        "thumbnail_url": str(raw["thumbnail_url"]).strip(),
        "source_url": source_url,
        "url": source_url,
        "media_type": media_type,
        "video_id": video_id,
        "thumbnail_path": "",
    }


def _read_cache_file() -> dict:
    if not DISCOVER_CACHE_FILE.exists():
        return {}
    try:
        data = json.loads(DISCOVER_CACHE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not read discover cache: %s", exc)
        return {}
    return data if isinstance(data, dict) else {}


def _write_cache_file(payload: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    DISCOVER_CACHE_FILE.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def get_cached_feed() -> list[dict]:
    """Return the last cached discover feed immediately (offline-safe)."""
    data = _read_cache_file()
    items = data.get("items")
    if not isinstance(items, list):
        return []
    return [dict(item) for item in items if isinstance(item, dict)]


def cache_is_stale(*, force: bool = False) -> bool:
    if force:
        return True
    data = _read_cache_file()
    fetched_at = data.get("fetched_at")
    try:
        fetched_ts = float(fetched_at)
    except (TypeError, ValueError):
        return True
    settings = _discover_settings()
    ttl_seconds = settings["cache_ttl_minutes"] * 60
    return (time.time() - fetched_ts) >= ttl_seconds


def _fetch_json(url: str, *, api_key: str = "") -> object:
    headers = {
        "User-Agent": _USER_AGENT,
        "Accept": "application/json",
    }
    if api_key:
        headers["X-Discover-Key"] = api_key
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=_FETCH_TIMEOUT) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        body = response.read().decode(charset, errors="replace")
    return json.loads(body)


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
    DISCOVER_THUMB_DIR.mkdir(parents=True, exist_ok=True)
    safe_id = hashlib.sha256(item_id.encode("utf-8")).hexdigest()[:16]
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(request, timeout=_THUMB_TIMEOUT) as response:
        data = response.read()
        ext = _guess_thumb_extension(response.headers.get("Content-Type", ""), url)
        target = DISCOVER_THUMB_DIR / f"{safe_id}{ext}"
        target.write_bytes(data)
        return str(target.resolve())


def _parse_feed_payload(payload: object, allowed_domains: list[str]) -> list[dict]:
    rows: list[object]
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        candidate = payload.get("items")
        rows = candidate if isinstance(candidate, list) else []
    else:
        raise ValueError("Discover feed must be a JSON array or an object with an 'items' array.")

    validated: list[dict] = []
    for raw in rows:
        item = _validate_item(raw, allowed_domains)
        if item is not None:
            validated.append(item)
    return validated


async def fetch_discover_feed(url: str | None = None) -> list[dict]:
    """Fetch discover JSON from *url* (or settings), validate, cache thumbnails."""
    settings = _discover_settings()
    feed_url = (url or _resolve_feed_url(settings)).strip()
    if not feed_url:
        raise ValueError(
            "Chưa cấu hình discover feed. Đặt discover_feed_url hoặc "
            "discover_feed_slug trong settings.json."
        )

    loop = asyncio.get_running_loop()
    try:
        payload = await loop.run_in_executor(
            None,
            lambda: _fetch_json(feed_url, api_key=settings["feed_api_key"]),
        )
    except urllib.error.HTTPError as exc:
        raise ValueError(f"Không thể tải feed Discover (HTTP {exc.code}).") from exc
    except urllib.error.URLError as exc:
        raise ValueError("Không thể kết nối tới feed Discover. Kiểm tra mạng.") from exc
    except json.JSONDecodeError as exc:
        raise ValueError("Feed Discover không phải JSON hợp lệ.") from exc
    except TimeoutError as exc:
        raise ValueError("Tải feed Discover quá thời gian chờ.") from exc

    items = _parse_feed_payload(payload, settings["allowed_domains"])
    if not items:
        logger.warning("Discover feed returned no valid items from %r", feed_url)

    cached_items: list[dict] = []
    for item in items:
        row = dict(item)
        thumb_url = row.get("thumbnail_url") or ""
        if thumb_url:
            try:
                row["thumbnail_path"] = await loop.run_in_executor(
                    None,
                    _download_thumbnail,
                    thumb_url,
                    row["id"],
                )
            except Exception as exc:
                logger.warning(
                    "Thumbnail download failed for discover item %r: %s",
                    row.get("id"),
                    exc,
                )
                row["thumbnail_path"] = ""
        cached_items.append(row)

    _write_cache_file({
        "fetched_at": time.time(),
        "feed_url": feed_url,
        "items": cached_items,
    })
    return cached_items
