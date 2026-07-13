"""Track collection and ordering for music playlist sharing."""

from __future__ import annotations

from pathlib import Path

from src.config import AUDIO_EXTS
from src.downloader import extract_youtube_id
from src.folder_order import apply_order
from src.metadata_store import get_metadata, read_embedded_metadata, resolve_display, resolve_source_url


def collect_playlist_tracks(playlist_root: Path) -> list[dict]:
    """Return audio tracks directly inside *playlist_root*, respecting custom order."""
    if not playlist_root.is_dir():
        return []

    rows: list[dict] = []
    for child in playlist_root.iterdir():
        if child.name.startswith("."):
            continue
        if child.is_dir():
            continue
        if child.suffix.lower() not in AUDIO_EXTS:
            continue

        meta_path = str(child.resolve())
        display = resolve_display(
            meta_path,
            default_title=child.stem,
            default_image="",
        )
        image = display["image"] or ""
        if not image:
            embedded = read_embedded_metadata(child)
            image = str(embedded.get("image") or "").strip()

        rows.append({
            "path": meta_path,
            "file_name": child.name,
            "title": display["title"],
            "artist": display["artist"],
            "image": image,
            "source_url": resolve_source_url(meta_path),
        })

    rows = apply_order(rows, playlist_root, key=lambda row: Path(str(row.get("path") or "")).name)
    for index, row in enumerate(rows, start=1):
        row["index"] = index
    return rows


def track_share_payload(row: dict) -> dict:
    source_url = str(row.get("source_url") or "").strip()
    thumbnail_url = str(row.get("image") or "").strip()
    if not thumbnail_url.startswith(("http://", "https://")):
        thumbnail_url = ""
    yt_id = extract_youtube_id(source_url)
    if yt_id and not thumbnail_url:
        thumbnail_url = f"https://i.ytimg.com/vi/{yt_id}/hqdefault.jpg"
    index = int(row.get("index") or 1)
    return {
        "index": index,
        "season": 1,
        "episode": index,
        "title": str(row.get("title") or f"Bài {index}"),
        "source_url": source_url,
        "thumbnail_url": thumbnail_url,
    }


def playlist_download_subdir(playlist_title: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in " -_" else "_" for ch in playlist_title).strip()
    return (safe[:80] or "Playlist").strip()
