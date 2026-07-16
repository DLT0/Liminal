import json
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter
from src.settings_store import CONFIG_DIR

TAGS_CACHE_FILE = CONFIG_DIR / "tags_cache.json"


def sync_tags_from_suggestions(items: list) -> None:
    """Scan all tags in suggestion items, aggregate usage count, and save to file."""
    counts = Counter()
    for item in items:
        if not isinstance(item, dict):
            continue
        tags = item.get("tags") or []
        for tag in tags:
            tag_cleaned = str(tag).strip().lower()
            if tag_cleaned:
                counts[tag_cleaned] += 1
                
    tags_list = []
    for name, count in counts.items():
        tags_list.append({"name": name, "usage_count": count})
        
    # Sort tags by usage_count descending, then by name alphabetically
    tags_list.sort(key=lambda x: (-x["usage_count"], x["name"]))
    
    data = {
        "tags": tags_list,
        "last_synced": datetime.now(timezone.utc).isoformat()
    }
    
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    TAGS_CACHE_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8"
    )


def get_tag_suggestions(prefix: str = "", limit: int = 10) -> list[str]:
    """Return tags matching the prefix sorted by usage_count descending."""
    if not TAGS_CACHE_FILE.exists():
        return []
    try:
        data = json.loads(TAGS_CACHE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
        
    if not isinstance(data, dict):
        return []
        
    tags = data.get("tags")
    if not isinstance(tags, list):
        return []
        
    prefix_lower = prefix.strip().lower()
    matching_tags = []
    
    for entry in tags:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or "").strip()
        count = int(entry.get("usage_count") or 0)
        if not name:
            continue
        if not prefix_lower or name.lower().startswith(prefix_lower):
            matching_tags.append((name, count))
            
    # Sort by usage_count descending, then by name alphabetically
    matching_tags.sort(key=lambda x: (-x[1], x[0]))
    
    return [t[0] for t in matching_tags[:limit]]
