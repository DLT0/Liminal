"""Helpers for validating music playlist share readiness."""

from __future__ import annotations

from pathlib import Path

from src import share_manager
from src.playlist_layout import collect_playlist_tracks


def playlist_share_block_reason(rows: list[dict] | None = None, *, folder: Path | None = None) -> str | None:
    """Return a user-facing error when a playlist folder cannot be shared."""
    if rows is None:
        if folder is None:
            return "Không tìm thấy playlist."
        rows = collect_playlist_tracks(folder)

    total = len(rows)
    if total == 0:
        return "Playlist không có bài hát nào."

    with_any_url = [row for row in rows if str(row.get("source_url") or "").strip()]
    allowed = [row for row in with_any_url if share_manager.is_allowed_share_url(str(row.get("source_url") or ""))]

    if allowed:
        return None

    if with_any_url:
        return (
            f"Có {len(with_any_url)}/{total} bài có link nhưng không hợp lệ. "
            "Chỉ hỗ trợ YouTube và Google Drive."
        )

    return (
        f"Không có bài nào chia sẻ được ({total} bài trong playlist). "
        "Tải bài qua trang Download để lưu link YouTube/Drive, "
        "hoặc sao chép file đã tải bằng Liminal vào playlist này."
    )
