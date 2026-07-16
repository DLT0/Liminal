import json
from pathlib import Path
from datetime import datetime
from src.settings_store import CONFIG_DIR
from src import podcast_library

def get_category_affinity() -> dict[str, float]:
    """Calculate category affinity based on total seconds listened (listened_position)."""
    affinity = {}

    # 1. Scan podcast_library.json
    library_data = podcast_library._read()
    items = library_data.get("items") or []
    for item in items:
        if not isinstance(item, dict):
            continue
        listened = float(item.get("listened_position") or 0.0)
        if listened <= 0:
            continue

        # Check category field or categories
        cats = item.get("categories") or []
        if not cats and item.get("category"):
            cats = [item["category"]]

        for cat in cats:
            cat_cleaned = str(cat).strip().lower()
            if cat_cleaned:
                affinity[cat_cleaned] = affinity.get(cat_cleaned, 0.0) + listened

    # 2. From podcast_library items (categories field)
    for item in library_data.get("items", []):
        if not isinstance(item, dict):
            continue
        listened = float(item.get("listened_position") or 0.0)
        if listened <= 0:
            continue

        cats = item.get("categories") or []
        if not cats and item.get("category"):
            cats = [item["category"]]

        for cat in cats:
            cat_cleaned = str(cat).strip().lower()
            if cat_cleaned:
                affinity[cat_cleaned] = affinity.get(cat_cleaned, 0.0) + listened

    return affinity


def get_recently_continued() -> list[dict]:
    """Return items that are partially listened (0 < position < 95% duration) sorted by recency."""
    continued = []

    # 1. From podcast_library.json
    library_data = podcast_library._read()
    for item in library_data.get("items", []):
        if not isinstance(item, dict):
            continue
        pos = float(item.get("listened_position") or 0.0)
        dur = float(item.get("duration_seconds") or 0.0)
        last_played = str(item.get("last_played_at") or "").strip()
        # Partially listened: pos > 0 and (dur == 0 or pos < 0.95 * dur)
        if pos > 0.0 and (dur == 0.0 or pos < 0.95 * dur):
            continued.append({
                "type": "library",
                "id": item.get("suggestion_id"),
                "title": item.get("title"),
                "path": item.get("path"),
                "author": item.get("author"),
                "thumbnail": item.get("thumbnail"),
                "last_played_at": last_played,
                "listened_position": pos,
                "duration_seconds": dur,
                "item": item
            })

    # 2. From podcasts.json
    podcasts_data = podcast_manager._load_podcasts_data()
    for feed in podcasts_data.get("feeds", []):
        for ep in feed.get("episodes", []):
            pos = float(ep.get("listened_position") or 0.0)
            dur = float(ep.get("duration_seconds") or 0.0)
            last_played = str(ep.get("last_played_at") or "").strip()
            if pos > 0.0 and (dur == 0.0 or pos < 0.95 * dur):
                continued.append({
                    "type": "rss",
                    "id": ep.get("guid"),
                    "title": ep.get("title"),
                    "path": ep.get("downloaded_path"),
                    "author": feed.get("title"),
                    "thumbnail": ep.get("image_url") or feed.get("image_url"),
                    "last_played_at": last_played,
                    "listened_position": pos,
                    "duration_seconds": dur,
                    "item": ep
                })

    # Sort by last_played_at descending (empty strings last)
    def sort_key(x):
        lp = x["last_played_at"]
        return lp if lp else "0000-00-00"

    continued.sort(key=sort_key, reverse=True)
    return continued
