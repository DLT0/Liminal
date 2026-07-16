"""Suggestions feed client and local cache for Liminal."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from src.settings_store import CONFIG_DIR

logger = logging.getLogger(__name__)

SHARE_API_BASE = "https://www.hoangminhduong.top"
_USER_AGENT = "Liminal/1.0"
_FETCH_TIMEOUT = 30
_THUMB_TIMEOUT = 15
_MAX_REDIRECTS = 5

SUGGESTIONS_FILE = CONFIG_DIR / "suggestions.json"
SUGGESTIONS_THUMB_DIR = Path(
    __import__("os").environ.get("XDG_CACHE_HOME", Path.home() / ".cache")
) / "liminal" / "suggestions"

# Fallback category labels used when the remote feed is unavailable.
# Thứ tự theo mức phổ biến (tham khảo Spotify / Apple Podcasts).
PODCAST_CATEGORIES: list[dict[str, str]] = [
    {"id": "tech", "label": "Công nghệ"},
    {"id": "business", "label": "Kinh doanh / Tài chính"},
    {"id": "education", "label": "Giáo dục"},
    {"id": "news", "label": "Tin tức / Thời sự"},
    {"id": "culture", "label": "Xã hội / Văn hóa"},
    {"id": "health", "label": "Sức khỏe / Tinh thần"},
    {"id": "entertainment", "label": "Giải trí"},
    {"id": "storytelling", "label": "Kể chuyện / True Crime"},
    {"id": "arts", "label": "Nghệ thuật / Sáng tạo"},
    {"id": "sports", "label": "Thể thao"},
    {"id": "science", "label": "Khoa học"},
    {"id": "personal", "label": "Phát triển bản thân"},
    {"id": "lifestyle", "label": "Đời sống / Gia đình"},
    {"id": "other", "label": "Khác"},
]

_CATEGORY_LABELS = {c["id"]: c["label"] for c in PODCAST_CATEGORIES}

_EPISODE_RE = re.compile(
    r"\b(?:Ep|EP|ep|T[âậạ]p|Episode|EPISODE|Season\s*\d+\s*Ep?)\s*\.?\s*(\d+)\b",
    re.IGNORECASE,
)


def _extract_episode_from_title(title: str) -> int:
    if not title:
        return 0
    m = _EPISODE_RE.search(title)
    if m:
        try:
            return int(m.group(1))
        except (ValueError, IndexError):
            pass
    return 0


def _item_sort_key(item: dict) -> tuple:
    season = max(1, int(item.get("season") or 1) or 1)
    episode = max(0, int(item.get("episode") or 0) or 0)
    if episode == 0:
        episode = _extract_episode_from_title(str(item.get("title") or ""))
    sort_order = max(0, int(item.get("sort_order") or 0) or 0)
    return (season, episode, sort_order)


def category_label(category_id: str | None, *, sections: list[dict[str, str]] | None = None) -> str:
    if not category_id:
        return ""
    if category_id in _CATEGORY_LABELS:
        return _CATEGORY_LABELS[category_id]
    for entry in sections or []:
        if str(entry.get("id") or "") == category_id:
            return str(entry.get("label") or category_id)
    return category_id


def _api_url(path: str) -> str:
    base = SHARE_API_BASE.rstrip("/")
    suffix = path if path.startswith("/") else f"/{path}"
    return f"{base}{suffix}"


def _migrate_suggestions_schema(data: dict) -> dict:
    if not isinstance(data, dict):
        return data
    items = data.get("items")
    if not isinstance(items, list):
        return data

    # Lấy section IDs từ data (nếu có) để detect playlist_id từ category cũ
    sections = data.get("sections") or []
    section_ids = {s["id"] for s in sections if isinstance(s, dict) and s.get("id")}

    migrated_items = []
    for item in items:
        if not isinstance(item, dict):
            migrated_items.append(item)
            continue

        migrated = dict(item)
        if "category" in migrated:
            cat_val = migrated.pop("category")
            if isinstance(cat_val, list):
                migrated["categories"] = cat_val
            else:
                migrated["categories"] = [str(cat_val).strip().lower()] if cat_val and str(cat_val).strip() else []
        elif "categories" not in migrated:
            migrated["categories"] = []

        if "category_label" in migrated:
            label_val = migrated.pop("category_label")
            if isinstance(label_val, list):
                migrated["category_labels"] = label_val
            else:
                migrated["category_labels"] = [str(label_val).strip()] if label_val and str(label_val).strip() else []
        elif "category_labels" not in migrated:
            migrated["category_labels"] = []

        if "playlist_id" not in migrated:
            # Detect: nếu category cũ là section ID thì dùng làm playlist_id
            cats = migrated.get("categories") or []
            candidates = [c for c in cats if c in section_ids]
            migrated["playlist_id"] = candidates[0] if candidates else None
            if candidates:
                migrated["categories"] = [c for c in cats if c not in section_ids]

        if "playlist_title" not in migrated:
            migrated["playlist_title"] = ""

        migrated_items.append(migrated)

    data["items"] = migrated_items
    return data


def _read_local_file() -> dict:
    if not SUGGESTIONS_FILE.exists():
        return {}
    try:
        data = json.loads(SUGGESTIONS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not read suggestions cache: %s", exc)
        return {}
    if not isinstance(data, dict):
        return {}

    needs_migrate = False
    items = data.get("items")
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict) and ("category" in item or "category_label" in item or "playlist_id" not in item or "playlist_title" not in item):
                needs_migrate = True
                break

    if needs_migrate:
        data = _migrate_suggestions_schema(data)
        try:
            _write_local_file(data)
        except Exception as exc:
            logger.warning("Could not save migrated suggestions cache: %s", exc)

    return data


def _write_local_file(payload: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    SUGGESTIONS_FILE.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def get_cached_items() -> list[dict]:
    data = _read_local_file()
    items = data.get("items")
    if not isinstance(items, list):
        return []
    return [dict(item) for item in items if isinstance(item, dict)]


def get_cached_categories() -> list[dict[str, str]]:
    data = _read_local_file()
    cats = data.get("categories")
    if isinstance(cats, list) and cats:
        out: list[dict[str, str]] = []
        seen: set[str] = set()
        for entry in cats:
            if not isinstance(entry, dict):
                continue
            cid = str(entry.get("id") or "").strip()
            cid_lower = cid.lower()
            label = str(entry.get("label") or "").strip()
            if cid and label and cid_lower not in seen:
                out.append({"id": cid, "label": label})
                seen.add(cid_lower)
        if out:
            return out
    return [dict(c) for c in PODCAST_CATEGORIES]


def get_cached_sections() -> list[dict[str, str]]:
    """Section kênh video do collaborator tạo."""
    data = _read_local_file()
    sections = data.get("sections")
    if not isinstance(sections, list):
        return []
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for entry in sections:
        if not isinstance(entry, dict):
            continue
        cid = str(entry.get("id") or "").strip()
        cid_lower = cid.lower()
        label = str(entry.get("label") or "").strip()
        if cid and label and cid_lower not in seen:
            out.append({"id": cid, "label": label})
            seen.add(cid_lower)
    return out


def _request_json(method: str, path: str, *, timeout: int = _FETCH_TIMEOUT) -> object:
    url = _api_url(path)
    headers = {
        "User-Agent": _USER_AGENT,
        "Accept": "application/json",
    }
    current_method = method

    for _ in range(_MAX_REDIRECTS):
        request = urllib.request.Request(url, headers=headers, method=current_method)
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
                continue
            raise
    raise ValueError("Quá nhiều lần chuyển hướng từ máy chủ đề xuất.")


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
    SUGGESTIONS_THUMB_DIR.mkdir(parents=True, exist_ok=True)
    safe_id = hashlib.sha256(item_id.encode("utf-8")).hexdigest()[:16]
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(request, timeout=_THUMB_TIMEOUT) as response:
        data = response.read()
        ext = _guess_thumb_extension(response.headers.get("Content-Type", ""), url)
        target = SUGGESTIONS_THUMB_DIR / f"{safe_id}{ext}"
        target.write_bytes(data)
        return str(target.resolve())


def _normalize_item(raw: dict, *, previous: dict | None = None, sections: list[dict[str, str]] | None = None) -> dict | None:
    item_id = str(raw.get("id") or "").strip()
    title = str(raw.get("title") or "").strip()
    source_url = str(
        raw.get("sourceUrl") or raw.get("source_url") or ""
    ).strip()
    if not item_id or not title or not source_url:
        return None

    content_type = str(
        raw.get("contentType") or raw.get("content_type") or "podcast"
    ).strip().lower()
    if content_type not in {"podcast", "video", "shorts"}:
        content_type = "podcast"

    media_kind = str(
        raw.get("mediaKind") or raw.get("media_kind") or "audio"
    ).strip().lower()
    if (media_kind not in {"audio", "video"}):
        media_kind = "audio"
    # Shorts luôn là video; Video/Podcast cho phép chọn MP3 (audio) hoặc video
    if content_type == "shorts":
        media_kind = "video"

    categories_raw = raw.get("categories") or raw.get("category")
    categories: list[str] = []
    if isinstance(categories_raw, list):
        categories = [str(c).strip().lower() for c in categories_raw if str(c).strip()]
    elif categories_raw is not None and str(categories_raw).strip():
        categories = [str(categories_raw).strip().lower()]

    # Detect section/playlist IDs in categories: nếu 1 category khớp với section ID
    # thì chuyển nó sang playlist_id (server cũ gửi section ID qua trường category)
    if sections is None:
        sections = get_cached_sections()
    section_ids = {s["id"] for s in sections if s.get("id")}

    # Chỉ tự động detect playlist_id nếu server không gửi playlist_id riêng
    explicit_playlist_id = raw.get("playlist_id") or raw.get("playlistId")
    if not explicit_playlist_id:
        playlist_candidates = [c for c in categories if c in section_ids]
        if playlist_candidates:
            # Dùng section ID đầu tiên khớp làm playlist_id
            raw = dict(raw)
            raw["playlist_id"] = playlist_candidates[0]
            # Loại section ID khỏi categories (giữ lại category cố định như tech, business...)
            categories = [c for c in categories if c not in section_ids]

    category_labels = [
        category_label(cid, sections=sections)
        for cid in categories
        if cid
    ]

    tags_raw = raw.get("tags")
    tags: list[str] = []
    if isinstance(tags_raw, list):
        tags = [str(t).strip().lower() for t in tags_raw if str(t).strip()][:5]

    thumb_url = str(
        raw.get("thumbnailUrl") or raw.get("thumbnail_url") or ""
    ).strip()
    local_thumb = ""
    if previous and str(previous.get("thumbnail_url") or "") == thumb_url:
        local_thumb = str(previous.get("local_thumbnail") or "")
    if thumb_url and not local_thumb:
        try:
            local_thumb = _download_thumbnail(thumb_url, item_id)
        except Exception as exc:
            logger.debug("Suggestion thumb download failed: %s", exc)

    prev_status = str((previous or {}).get("download_status") or "pending")
    prev_percent = float((previous or {}).get("download_percent") or 0.0)
    local_path = str((previous or {}).get("local_path") or "").strip()

    playlist_id = raw.get("playlist_id") or raw.get("playlistId")
    if playlist_id is not None:
        playlist_id = str(playlist_id).strip()
        if not playlist_id:
            playlist_id = None
    else:
        playlist_id = None

    playlist_title = raw.get("playlist_title") or raw.get("playlistTitle")
    if playlist_title is not None:
        playlist_title = str(playlist_title).strip()
    else:
        playlist_title = ""

    return {
        "id": item_id,
        "title": title,
        "author": str(raw.get("author") or "").strip(),
        "description": str(raw.get("description") or "").strip(),
        "thumbnail_url": thumb_url,
        "local_thumbnail": local_thumb,
        "source_url": source_url,
        "content_type": content_type,
        "media_kind": media_kind,
        "categories": categories,
        "category_labels": category_labels,
        "playlist_id": playlist_id,
        "playlist_title": playlist_title,
        "tags": tags,
        "sort_order": max(0, int(raw.get("sortOrder") or raw.get("sort_order") or 0) or 0),
        "season": max(1, int(raw.get("season") or 1) or 1),
        "episode": max(0, int(raw.get("episode") or 0) or 0),
        "collaborator_name": str(
            raw.get("collaboratorName") or raw.get("collaborator_name") or ""
        ).strip(),
        "created_at": str(raw.get("createdAt") or raw.get("created_at") or ""),
        "download_status": prev_status if prev_status in {"pending", "downloading", "done", "error"} else "pending",
        "download_percent": prev_percent,
        "is_downloading": prev_status == "downloading",
        "local_path": local_path,
    }


def _fetch_categories_sync() -> list[dict[str, str]]:
    try:
        payload = _request_json("GET", "/api/suggestions/categories")
    except Exception as exc:
        logger.warning("Could not fetch suggestion categories: %s", exc)
        return get_cached_categories()
    if not isinstance(payload, dict):
        return get_cached_categories()
    cats = payload.get("categories")
    if not isinstance(cats, list):
        return get_cached_categories()
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for entry in cats:
        if not isinstance(entry, dict):
            continue
        cid = str(entry.get("id") or "").strip()
        cid_lower = cid.lower()
        label = str(entry.get("label") or "").strip()
        if cid and label and cid_lower not in seen:
            out.append({"id": cid, "label": label})
            seen.add(cid_lower)
    return out or get_cached_categories()


def _fetch_suggestions_sync(*, content_type: str | None = None, sections: list[dict[str, str]] | None = None) -> list[dict]:
    path = "/api/suggestions?limit=100"
    if content_type in {"podcast", "video", "shorts"}:
        path += f"&contentType={content_type}"
    try:
        payload = _request_json("GET", path)
    except Exception as exc:
        logger.warning("Could not fetch suggestions: %s", exc)
        return list(get_cached_items())
    if not isinstance(payload, dict):
        logger.warning("Suggestions response invalid, falling back to cache.")
        return list(get_cached_items())
    items = payload.get("items")
    if not isinstance(items, list):
        return []
    previous_by_id = {
        str(item.get("id") or ""): item
        for item in get_cached_items()
        if isinstance(item, dict)
    }
    normalized: list[dict] = []
    seen_ids: set[str] = set()
    seen_urls: set[str] = set()
    for entry in items:
        if not isinstance(entry, dict):
            continue
        item_id = str(entry.get("id") or "").strip()
        source_url = str(entry.get("sourceUrl") or entry.get("source_url") or "").strip()
        if item_id in seen_ids or (source_url and source_url in seen_urls):
            continue
        seen_ids.add(item_id)
        if source_url:
            seen_urls.add(source_url)
        item = _normalize_item(
            entry,
            previous=previous_by_id.get(item_id),
            sections=sections,
        )
        if item is not None:
            normalized.append(item)
    return normalized


def _fetch_sections_sync() -> list[dict[str, str]]:
    try:
        payload = _request_json("GET", "/api/suggestions/sections")
    except Exception as exc:
        logger.warning("Could not fetch video sections: %s", exc)
        return get_cached_sections()
    if not isinstance(payload, dict):
        return get_cached_sections()
    sections = payload.get("sections")
    if not isinstance(sections, list):
        return get_cached_sections()
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for entry in sections:
        if not isinstance(entry, dict):
            continue
        cid = str(entry.get("id") or "").strip()
        cid_lower = cid.lower()
        label = str(entry.get("label") or "").strip()
        if cid and label and cid_lower not in seen:
            out.append({"id": cid, "label": label})
            seen.add(cid_lower)
    return out


async def refresh_suggestions() -> list[dict]:
    """Fetch published suggestions + categories + sections; update on-disk cache."""
    # Fetch categories and sections first to ensure they are available for suggestions normalization
    categories, sections = await asyncio.gather(
        asyncio.to_thread(_fetch_categories_sync),
        asyncio.to_thread(_fetch_sections_sync),
    )
    items = await asyncio.to_thread(_fetch_suggestions_sync, sections=sections)
    # Ghi sections trước rồi normalize lại labels nếu cần
    _write_local_file({
        "items": items,
        "categories": categories,
        "sections": sections,
    })
    # Cập nhật category_labels sau khi có sections mới
    for item in items:
        if not isinstance(item, dict):
            continue
        cids = item.get("categories") or []
        item["category_labels"] = [
            category_label(cid, sections=sections)
            for cid in cids
            if cid
        ]
    _write_local_file({
        "items": items,
        "categories": categories,
        "sections": sections,
    })

    try:
        from src.tag_store import sync_tags_from_suggestions
        sync_tags_from_suggestions(items)
    except Exception as exc:
        logger.warning("Could not sync tags: %s", exc)

    return items


def list_suggestions(
    *,
    content_type: str | None = None,
    category: str | None = None,
) -> list[dict]:
    """Return cached suggestions filtered in-process.

    ``category`` matches against both the ``tags`` list (multi-category)
    and the ``categories`` list (playlist/section ID).
    """
    items = get_cached_items()
    out: list[dict] = []
    for item in items:
        ct = str(item.get("content_type") or "")
        if content_type and ct != content_type:
            continue
        if category and category != "all":
            cats = item.get("categories") or []
            tags = item.get("tags") or []
            if category not in cats and category not in tags:
                continue
        out.append(dict(item))
    return out


def persist_download_state(
    suggestion_id: str,
    *,
    status: str | None = None,
    percent: float | None = None,
    is_downloading: bool | None = None,
    local_path: str | None = None,
) -> list[dict]:
    """Patch one cached suggestion's download fields and rewrite cache."""
    data = _read_local_file()
    items = data.get("items")
    if not isinstance(items, list):
        return []
    needle = (suggestion_id or "").strip()
    for item in items:
        if not isinstance(item, dict):
            continue
        if str(item.get("id") or "") != needle:
            continue
        if status is not None:
            item["download_status"] = status
        if percent is not None:
            item["download_percent"] = float(percent)
        if is_downloading is not None:
            item["is_downloading"] = bool(is_downloading)
        if local_path is not None:
            item["local_path"] = str(local_path)
        break
    _write_local_file(data)
    return [dict(i) for i in items if isinstance(i, dict)]


def get_local_path(suggestion_id: str) -> str:
    needle = (suggestion_id or "").strip()
    if not needle:
        return ""
    for item in get_cached_items():
        if str(item.get("id") or "") == needle:
            path = str(item.get("local_path") or "").strip()
            return path
    return ""


def get_items_by_category(category_id: str) -> list[dict]:
    """Trả về mọi item gợi ý có category_id nằm trong mảng categories, sắp xếp theo season và episode tăng dần."""
    cid = (category_id or "").strip().lower()
    if not cid:
        return []
    items = get_cached_items()
    out = []
    for item in items:
        cats = item.get("categories") or []
        if cid in cats:
            out.append(dict(item))
    out.sort(key=_item_sort_key)
    return out


def get_items_by_playlist(playlist_id: str) -> list[dict]:
    """Trả về mọi item gợi ý có playlist_id khớp, sắp xếp theo season và episode tăng dần."""
    pid = (playlist_id or "").strip()
    if not pid:
        return []
    items = get_cached_items()
    out = []
    for item in items:
        if item.get("playlist_id") == pid:
            out.append(dict(item))
    out.sort(key=_item_sort_key)
    return out


def get_playlists() -> list[dict]:
    """Gom nhóm tất cả gợi ý theo playlist_id (bỏ qua playlist_id trống).

    Trả về danh sách các playlist chứa: playlist_id, title, item_count, thumbnail.
    - Lấy tên playlist từ playlist_title field (không phải tên tập)
    - Lọc bỏ playlist có 0 items
    - Sắp xếp theo size (>=3 videos) và playlist_id
    """
    items = get_cached_items()
    groups = {}
    for item in items:
        pid = item.get("playlist_id")
        if pid:
            pid = str(pid).strip()
            if pid:
                if pid not in groups:
                    groups[pid] = []
                groups[pid].append(item)
                
    out = []
    for pid, group in groups.items():
        # Bỏ qua playlist nếu chỉ có 0 items
        if not group:
            continue

        def sort_key(item):
            season = max(1, int(item.get("season") or 1) or 1)
            episode = max(0, int(item.get("episode") or 0) or 0)
            if episode == 0:
                episode = _extract_episode_from_title(str(item.get("title") or ""))
            sort_order = max(0, int(item.get("sort_order") or 0) or 0)
            return (season, episode, sort_order)
            
        group.sort(key=sort_key)
        first_item = group[0]
        
        # Lấy playlist_title - ưu tiên: playlist_title field > section label > item title > playlist_id
        title = str(first_item.get("playlist_title") or "").strip()
        if not title:
            # Fallback: thử lấy tên từ các item khác nếu có
            for item_in_group in group:
                alt_title = str(item_in_group.get("playlist_title") or "").strip()
                if alt_title:
                    title = alt_title
                    break

        if not title:
            # Fallback: tìm section label từ sections cache
            sections = get_cached_sections()
            for section in sections:
                if section.get("id") == pid:
                    title = str(section.get("label") or "").strip()
                    break

        if not title:
            # Nếu vẫn không có, dùng title của first_item (tên tập)
            title = str(first_item.get("title") or "").strip()

        if not title:
            title = pid
            
        thumbnail = str(first_item.get("local_thumbnail") or first_item.get("thumbnail_url") or "").strip()
        
        out.append({
            "playlist_id": pid,
            "title": title,
            "item_count": len(group),
            "thumbnail": thumbnail
        })
        
    # Sắp xếp: trước là playlist >=3 videos, sau là những cái nhỏ hơn
    out.sort(key=lambda x: (-(x["item_count"] >= 3), x["playlist_id"].lower()))
    return out


def get_ungrouped_suggestions() -> list[dict]:
    """Trả về các item gợi ý không thuộc playlist nào (ungrouped suggestions).
    
    Đây là các item chỉ có category, không có playlist_id.
    Lọc bỏ những item đã tải về (có local_path).
    """
    items = get_cached_items()
    out = []
    for item in items:
        # Bỏ qua item có playlist_id
        if item.get("playlist_id"):
            continue
        # Bỏ qua item đã tải về
        local_path = str(item.get("local_path") or "").strip()
        if local_path:
            continue
        out.append(dict(item))
    return out


def get_categories_with_counts() -> list[dict]:
    """Trả về danh sách category với số lượng item trong mỗi category.
    
    Chỉ bao gồm category có ít nhất 1 item.
    Format: [{"id": str, "label": str, "item_count": int}, ...]
    """
    items = get_cached_items()
    categories = get_cached_categories()
    
    # Đếm item per category
    category_counts: dict[str, int] = {}
    for item in items:
        cats = item.get("categories") or []
        for cat in cats:
            category_counts[cat] = category_counts.get(cat, 0) + 1
    
    # Chỉ trả về category có item
    result = []
    for cat_info in categories:
        cat_id = str(cat_info.get("id") or "").strip().lower()
        count = category_counts.get(cat_id, 0)
        if count > 0:
            result.append({
                "id": cat_id,
                "label": str(cat_info.get("label") or ""),
                "item_count": count
            })
    
    return result


def import_youtube_playlist(url: str, media_kind: str = "audio") -> dict:
    import hashlib
    from datetime import datetime, timezone
    
    # Validation
    cleaned_url = url.strip()
    if "list=" not in cleaned_url:
        raise ValueError("URL không chứa 'list=' (không phải playlist YouTube hợp lệ)")
    
    # Construct playlist_id
    hasher = hashlib.md5(cleaned_url.encode("utf-8"))
    playlist_id = f"yt_{hasher.hexdigest()[:8]}"
    
    try:
        import yt_dlp
    except ImportError:
        raise ValueError("Thư viện yt_dlp chưa được cài đặt.")
        
    ydl_opts = {
        'extract_flat': True,
        'skip_download': True,
        'quiet': True,
        'no_warnings': True,
    }
    
    logger.info("Extracting YouTube playlist: %s", cleaned_url)
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(cleaned_url, download=False)
    except Exception as exc:
        logger.warning("Failed to extract YouTube playlist: %s", exc)
        raise ValueError(f"Không thể tải playlist YouTube. Lỗi: {exc}")
        
    if not info:
        raise ValueError("Không tìm thấy thông tin playlist YouTube.")
        
    playlist_title = info.get("title") or "YouTube Playlist"
    entries = info.get("entries") or []
    if not entries:
        raise ValueError("Playlist YouTube rỗng hoặc không có video hợp lệ.")
        
    has_warning = False
    if len(entries) > 100:
        entries = entries[:100]
        has_warning = True
        
    import_items = []
    for idx, entry in enumerate(entries):
        if not entry:
            continue
        video_id = entry.get("id") or entry.get("url")
        if not video_id:
            continue
        video_title = entry.get("title") or "Unnamed Video"
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        
        # Resolve thumbnail
        thumbnail = entry.get("thumbnail") or ""
        if not thumbnail and entry.get("thumbnails"):
            thumbnail = entry["thumbnails"][0].get("url") or ""
            
        duration = float(entry.get("duration") or 0.0)
        uploader = entry.get("uploader") or entry.get("author") or ""
        
        import_item = {
            "id": f"yt_{video_id}",
            "content_type": "podcast",
            "media_kind": "audio" if media_kind == "audio" else "video",
            "categories": [],
            "category_labels": [],
            "playlist_id": playlist_id,
            "playlist_title": playlist_title,
            "title": video_title,
            "author": uploader,
            "source_url": video_url,
            "thumbnail_url": thumbnail,
            "duration_seconds": duration,
            "season": 1,
            "episode": idx + 1,
            "source": "user_import",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        import_items.append(import_item)
        
    if not import_items:
        raise ValueError("Không tìm thấy video hợp lệ trong playlist.")
        
    # Read cache and merge
    cache = _read_local_file()
    items = cache.get("items") or []
    
    existing_ids = {item["id"] for item in items if isinstance(item, dict) and "id" in item}
    new_items = []
    for item in import_items:
        if item["id"] not in existing_ids:
            new_items.append(item)
            
    if new_items:
        items.extend(new_items)
        cache["items"] = items
        _write_local_file(cache)
        
    return {
        "playlist_id": playlist_id,
        "playlist_title": playlist_title,
        "item_count": len(import_items),
        "imported_count": len(new_items),
        "warning": "Playlist quá lớn (>100 video), chỉ lấy 100 video đầu tiên." if has_warning else ""
    }
