"""Season / episode detection and ordering for TV series libraries."""

from __future__ import annotations

import re
from pathlib import Path

from src.config import VIDEO_EXTS
from src.downloader import extract_youtube_id
from src.metadata_store import get_metadata, read_video_thumbnail, resolve_display, resolve_source_url, set_metadata

_SEASON_PATTERNS = (
    re.compile(r"(?i)(?:season|mùa|mua|ss)\s*0*(\d{1,2})"),
    re.compile(r"(?i)\bs0*(\d{1,2})\b"),
)
_EPISODE_PATTERNS = (
    re.compile(r"(?i)(?:episode|ep|tập|tap)\s*0*(\d{1,3})"),
    re.compile(r"(?i)\be0*(\d{1,3})\b"),
    re.compile(r"(?i)(?:^|[.\-_\[\( ])0*(\d{1,3})(?:[.\-_\]\) ]|$)"),
)
_SXXEXX_PATTERN = re.compile(
    r"(?i)(?:^|[.\-_ \[])"
    r"(?:s(?P<s>\d{1,2})[ex](?P<e>\d{1,3})|(?P<s2>\d{1,2})x(?P<e2>\d{1,3}))"
)


def _first_match(patterns: tuple[re.Pattern[str], ...], text: str) -> int | None:
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            value = next((g for g in match.groups() if g), None)
            if value:
                return int(value)
    return None


def parse_season_number(text: str) -> int | None:
    return _first_match(_SEASON_PATTERNS, text or "")


def parse_episode_number(text: str) -> int | None:
    match = _SXXEXX_PATTERN.search(text or "")
    if match:
        episode = match.group("e") or match.group("e2")
        if episode:
            return int(episode)
    return _first_match(_EPISODE_PATTERNS, text or "")


def parse_season_episode_from_name(name: str) -> tuple[int | None, int | None]:
    match = _SXXEXX_PATTERN.search(name or "")
    if not match:
        return None, parse_episode_number(name)
    season_raw = match.group("s") or match.group("s2")
    episode_raw = match.group("e") or match.group("e2")
    season = int(season_raw) if season_raw else None
    episode = int(episode_raw) if episode_raw else None
    return season, episode


def _stored_int(meta: dict, key: str) -> int | None:
    raw = meta.get(key)
    if raw is None or raw == "":
        return None
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        return None


def resolve_season_episode(path: Path, series_root: Path, *, use_metadata: bool = True) -> tuple[int, int]:
    meta_path = str(path.resolve())
    season: int | None = None
    episode: int | None = None
    if use_metadata:
        meta = get_metadata(meta_path)
        season = _stored_int(meta, "season")
        episode = _stored_int(meta, "episode")

    try:
        relative = path.resolve().relative_to(series_root.resolve())
    except ValueError:
        relative = Path(path.name)

    context_parts = list(relative.parts[:-1]) + [path.stem]
    context_text = " ".join(context_parts)

    if season is None:
        if len(relative.parts) > 1:
            season = parse_season_number(relative.parts[0])
        if season is None:
            auto_season, _ = parse_season_episode_from_name(context_text)
            season = auto_season
    if episode is None:
        _, auto_episode = parse_season_episode_from_name(path.stem)
        episode = auto_episode or parse_episode_number(path.stem)

    return max(1, int(season or 1)), max(1, int(episode or 1))


def format_episode_subtitle(*, season: int, episode: int, extra: str = "") -> str:
    parts: list[str] = []
    if season > 1:
        parts.append(f"Mùa {season}")
    parts.append(f"Tập {episode}")
    label = " · ".join(parts)
    extra = (extra or "").strip()
    if extra and extra.lower() not in label.lower():
        return f"{label} · {extra}"
    return label


def episode_sort_key(row: dict) -> tuple[int, int, str]:
    return (
        int(row.get("season") or 1),
        int(row.get("episode") or 1),
        str(row.get("path") or "").lower(),
    )


def collect_series_videos(series_root: Path, *, use_metadata: bool = True) -> list[dict]:
    """Return all episodes under *series_root*, sorted by season then episode."""
    if not series_root.is_dir():
        return []

    rows: list[dict] = []
    for file_path in series_root.rglob("*"):
        if not file_path.is_file() or file_path.suffix.lower() not in VIDEO_EXTS:
            continue
        season, episode = resolve_season_episode(file_path, series_root, use_metadata=use_metadata)
        meta_path = str(file_path.resolve())
        try:
            relative = file_path.resolve().relative_to(series_root.resolve())
        except ValueError:
            relative = Path(file_path.name)
        display = resolve_display(
            meta_path,
            default_title=file_path.stem,
            default_image=read_video_thumbnail(file_path),
        )
        rows.append({
            "path": meta_path,
            "file_name": file_path.name,
            "relative_path": str(relative),
            "title": display["title"],
            "artist": display["artist"],
            "image": display["image"] or read_video_thumbnail(file_path),
            "season": season,
            "episode": episode,
            "subtitle": format_episode_subtitle(season=season, episode=episode),
            "source_url": resolve_source_url(meta_path),
        })

    rows.sort(key=episode_sort_key)
    for index, row in enumerate(rows, start=1):
        row["index"] = index
    return rows


def detect_series_rows(series_root: Path) -> list[dict]:
    return collect_series_videos(series_root, use_metadata=False)


def save_series_rows(rows: list[dict]) -> None:
    for row in rows:
        path = str(row.get("path") or "").strip()
        if not path:
            continue
        fields: dict[str, str] = {
            "season": str(int(row.get("season") or 1)),
            "episode": str(int(row.get("episode") or 1)),
        }
        title = str(row.get("title") or "").strip()
        if title:
            fields["title"] = title
        set_metadata(path, **fields)


def episode_share_payload(row: dict) -> dict:
    source_url = str(row.get("source_url") or "").strip()
    thumbnail_url = ""
    yt_id = extract_youtube_id(source_url)
    if yt_id:
        thumbnail_url = f"https://i.ytimg.com/vi/{yt_id}/hqdefault.jpg"
    season = int(row.get("season") or 1)
    episode = int(row.get("episode") or row.get("index") or 1)
    return {
        "index": int(row.get("index") or episode),
        "season": season,
        "episode": episode,
        "title": str(row.get("title") or f"Tập {episode}"),
        "source_url": source_url,
        "thumbnail_url": thumbnail_url,
    }


def episode_download_subdir(series_title: str, *, season: int) -> str:
    safe = "".join(ch if ch.isalnum() or ch in " -_" else "_" for ch in series_title).strip()
    base = (safe[:80] or "Phim bộ").strip()
    if season > 1:
        return f"{base}/Mùa {season}"
    return base


def rows_to_ai_payload(rows: list[dict]) -> list[dict]:
    payload: list[dict] = []
    for index, row in enumerate(rows):
        path = str(row.get("path") or "")
        file_name = str(row.get("file_name") or Path(path).name if path else "")
        payload.append({
            "id": str(index),
            "fileName": file_name,
            "title": str(row.get("title") or file_name),
            "relativePath": str(row.get("relative_path") or ""),
        })
    return payload


def apply_ai_sort_results(rows: list[dict], ai_rows: list[dict]) -> list[dict]:
    by_id: dict[str, dict] = {}
    for entry in ai_rows:
        if not isinstance(entry, dict):
            continue
        row_id = str(entry.get("id") or "").strip()
        if row_id:
            by_id[row_id] = entry

    updated: list[dict] = []
    for index, row in enumerate(rows):
        merged = dict(row)
        ai = by_id.get(str(index), {})
        season = max(1, int(ai.get("season") or merged.get("season") or 1))
        episode = max(1, int(ai.get("episode") or merged.get("episode") or 1))
        sort_order = int(ai.get("sort_order") or index + 1)
        merged["season"] = season
        merged["episode"] = episode
        merged["sort_order"] = sort_order
        ai_title = str(ai.get("title") or "").strip()
        if ai_title:
            merged["title"] = ai_title
        merged["subtitle"] = format_episode_subtitle(season=season, episode=episode)
        updated.append(merged)

    updated.sort(key=lambda row: int(row.get("sort_order") or 0))
    for index, row in enumerate(updated, start=1):
        row["index"] = index
    return updated


def apply_tap_assignments(rows: list[dict], assignments: list[dict]) -> list[dict]:
    by_path = {str(row.get("path") or ""): dict(row) for row in rows}
    for item in assignments:
        path = str(item.get("path") or "").strip()
        if not path or path not in by_path:
            continue
        base = by_path[path]
        season = max(1, int(item.get("season") or 1))
        episode = max(1, int(item.get("episode") or 1))
        base["season"] = season
        base["episode"] = episode
        base["subtitle"] = format_episode_subtitle(season=season, episode=episode)
    updated = list(by_path.values())
    updated.sort(key=episode_sort_key)
    for index, row in enumerate(updated, start=1):
        row["index"] = index
    return updated


def apply_tap_order(rows: list[dict], ordered_paths: list[str], *, season: int = 1) -> list[dict]:
    """Assign episode numbers by tap order within a single season."""
    by_path = {str(row.get("path") or ""): dict(row) for row in rows}
    updated: list[dict] = []
    for episode_no, path in enumerate(ordered_paths, start=1):
        base = by_path.get(path)
        if base is None:
            continue
        base["season"] = max(1, int(season))
        base["episode"] = episode_no
        base["subtitle"] = format_episode_subtitle(season=base["season"], episode=episode_no)
        updated.append(base)

    for row in rows:
        path = str(row.get("path") or "")
        if path not in ordered_paths:
            updated.append(dict(row))

    updated.sort(key=episode_sort_key)
    for index, row in enumerate(updated, start=1):
        row["index"] = index
    return updated
