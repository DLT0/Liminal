from dataclasses import dataclass, field, asdict
import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path

from src.settings_store import CONFIG_DIR, get_podcasts_dir

logger = logging.getLogger(__name__)

PODCAST_LIBRARY_FILE = CONFIG_DIR / "podcast_library.json"
_library_lock = threading.RLock()


@dataclass
class PodcastLibraryItem:
    suggestion_id: str
    title: str
    path: str
    author: str = ""
    media_kind: str = "audio"
    category: str = ""
    category_label: str = ""
    thumbnail: str = ""
    source_url: str = ""
    description: str = ""
    downloaded_at: str = ""
    listened_position: float = 0.0
    duration_seconds: float = 0.0
    last_played_at: str = ""
    play_count: int = 0


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _migrate_library_schema(data: dict) -> dict:
    if not isinstance(data, dict):
        return data
    items = data.get("items")
    if not isinstance(items, list):
        return data

    migrated_items = []
    for item in items:
        if not isinstance(item, dict):
            migrated_items.append(item)
            continue

        migrated = dict(item)
        if "listened_position" not in migrated:
            migrated["listened_position"] = 0.0
        if "duration_seconds" not in migrated:
            migrated["duration_seconds"] = 0.0
        if "last_played_at" not in migrated:
            migrated["last_played_at"] = ""
        if "play_count" not in migrated:
            migrated["play_count"] = 0

        migrated_items.append(migrated)

    data["items"] = migrated_items
    return data


def _read() -> dict:
    with _library_lock:
        if not PODCAST_LIBRARY_FILE.exists():
            return {"items": []}
        try:
            data = json.loads(PODCAST_LIBRARY_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not read podcast library: %s", exc)
            return {"items": []}
        if not isinstance(data, dict):
            return {"items": []}

        # Check if migration is needed
        needs_migrate = False
        items = data.get("items")
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict) and any(f not in item for f in ("listened_position", "duration_seconds", "last_played_at", "play_count")):
                    needs_migrate = True
                    break

        if needs_migrate:
            data = _migrate_library_schema(data)
            try:
                _write(data)
            except Exception as exc:
                logger.warning("Could not write migrated podcast library: %s", exc)

        return data


def _write(data: dict) -> None:
    with _library_lock:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        temp_file = PODCAST_LIBRARY_FILE.with_suffix(".tmp")
        temp_file.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temp_file.replace(PODCAST_LIBRARY_FILE)


def list_downloads() -> list[dict]:
    """Return downloaded podcast suggestion rows (existing files only)."""
    data = _read()
    items = data.get("items")
    if not isinstance(items, list):
        return []
    out: list[dict] = []
    changed = False
    kept: list[dict] = []
    for entry in items:
        if not isinstance(entry, dict):
            changed = True
            continue
        path = str(entry.get("path") or "").strip()
        if not path or not Path(path).exists():
            changed = True
            continue
        kept.append(entry)
        out.append(dict(entry))
    if changed:
        data["items"] = kept
        _write(data)
    return out


def get_by_suggestion_id(suggestion_id: str) -> dict | None:
    needle = (suggestion_id or "").strip()
    if not needle:
        return None
    for item in list_downloads():
        if str(item.get("suggestion_id") or "") == needle:
            return item
    return None


def get_path_for_suggestion(suggestion_id: str) -> str:
    item = get_by_suggestion_id(suggestion_id)
    if not item:
        return ""
    path = str(item.get("path") or "").strip()
    return path if path and Path(path).exists() else ""


def register_download(
    *,
    suggestion_id: str,
    title: str,
    author: str = "",
    path: str,
    media_kind: str = "audio",
    category: str = "",
    category_label: str = "",
    thumbnail: str = "",
    source_url: str = "",
    description: str = "",
    listened_position: float = 0.0,
    duration_seconds: float = 0.0,
    last_played_at: str = "",
    play_count: int = 0,
) -> dict:
    """Upsert a downloaded podcast suggestion file."""
    sid = (suggestion_id or "").strip()
    resolved = str(Path(path).expanduser().resolve()) if path else ""
    if not sid or not resolved or not Path(resolved).exists():
        raise ValueError("suggestion_id và path hợp lệ là bắt buộc")

    data = _read()
    items = data.get("items")
    if not isinstance(items, list):
        items = []

    # Check for existing item to merge playback fields if needed
    existing_item = None
    for existing in items:
        if isinstance(existing, dict) and str(existing.get("suggestion_id") or "") == sid:
            existing_item = existing
            break

    # If the caller didn't provide specific values but we have existing ones, preserve them
    resolved_listened_position = listened_position
    resolved_duration_seconds = duration_seconds
    resolved_last_played_at = last_played_at
    resolved_play_count = play_count

    if existing_item:
        if listened_position == 0.0 and "listened_position" in existing_item:
            resolved_listened_position = float(existing_item["listened_position"])
        if duration_seconds == 0.0 and "duration_seconds" in existing_item:
            resolved_duration_seconds = float(existing_item["duration_seconds"])
        if not last_played_at and "last_played_at" in existing_item:
            resolved_last_played_at = str(existing_item["last_played_at"])
        if play_count == 0 and "play_count" in existing_item:
            resolved_play_count = int(existing_item["play_count"])

    item_obj = PodcastLibraryItem(
        suggestion_id=sid,
        title=(title or "").strip() or Path(resolved).stem,
        author=(author or "").strip(),
        path=resolved,
        media_kind="video" if media_kind == "video" else "audio",
        category=(category or "").strip(),
        category_label=(category_label or "").strip(),
        thumbnail=(thumbnail or "").strip(),
        source_url=(source_url or "").strip(),
        description=(description or "").strip(),
        downloaded_at=_now_iso(),
        listened_position=resolved_listened_position,
        duration_seconds=resolved_duration_seconds,
        last_played_at=resolved_last_played_at,
        play_count=resolved_play_count,
    )
    row = asdict(item_obj)

    replaced = False
    for i, existing in enumerate(items):
        if isinstance(existing, dict) and str(existing.get("suggestion_id") or "") == sid:
            items[i] = row
            replaced = True
            break
    if not replaced:
        items.insert(0, row)

    data["items"] = items
    _write(data)
    return row


def update_playback_state(
    suggestion_id: str,
    *,
    listened_position: float | None = None,
    duration_seconds: float | None = None,
    last_played_at: str | None = None,
    play_count: int | None = None,
) -> dict | None:
    """Update playback statistics for a library item."""
    sid = (suggestion_id or "").strip()
    if not sid:
        return None
    data = _read()
    items = data.get("items")
    if not isinstance(items, list):
        return None
    for existing in items:
        if isinstance(existing, dict) and str(existing.get("suggestion_id") or "") == sid:
            if listened_position is not None:
                existing["listened_position"] = float(listened_position)
            if duration_seconds is not None:
                existing["duration_seconds"] = float(duration_seconds)
            if last_played_at is not None:
                existing["last_played_at"] = str(last_played_at)
            if play_count is not None:
                existing["play_count"] = int(play_count)
            _write(data)
            return dict(existing)
    return None


def update_progress(suggestion_id: str, position: float, duration: float) -> None:
    """Update listened progress/duration for a library suggestion."""
    update_playback_state(suggestion_id, listened_position=position, duration_seconds=duration)


def increment_play_count(suggestion_id: str) -> None:
    """Increment play count and update last_played_at for a library suggestion."""
    item = get_by_suggestion_id(suggestion_id)
    current_count = int(item.get("play_count") or 0) if item else 0
    update_playback_state(
        suggestion_id,
        play_count=current_count + 1,
        last_played_at=datetime.now(timezone.utc).isoformat(),
    )


def list_watched() -> list[dict]:
    """Return all library items sorted by last_played_at descending, only if they have been played."""
    data = _read()
    items = data.get("items")
    if not isinstance(items, list):
        return []
    out: list[dict] = []
    for entry in items:
        if not isinstance(entry, dict):
            continue
        last = str(entry.get("last_played_at") or "")
        if not last:
            continue
        out.append(dict(entry))
    out.sort(key=lambda x: str(x.get("last_played_at") or ""), reverse=True)
    return out


def remove_file_keep_metadata(suggestion_id: str) -> bool:
    """Delete the actual file for a library entry but keep the metadata for watched history."""
    item = get_by_suggestion_id(suggestion_id)
    if not item:
        return False
    path = str(item.get("path") or "").strip()
    if path:
        try:
            Path(path).unlink(missing_ok=True)
        except OSError:
            pass
        # Also try to clean up thumbnail/info json sidecars
        for suffix in (".jpg", ".webp", ".png", ".info.json"):
            sidecar = Path(path).with_suffix(suffix)
            try:
                sidecar.unlink(missing_ok=True)
            except OSError:
                pass



def ensure_podcasts_dir() -> Path:
    path = get_podcasts_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path
