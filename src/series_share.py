"""Helpers for validating series share readiness."""

from __future__ import annotations

from pathlib import Path

from src import share_manager
from src.series_layout import collect_series_videos


def series_share_block_reason(rows: list[dict] | None = None, *, folder: Path | None = None) -> str | None:
    """Return a user-facing error when a series folder cannot be shared."""
    if rows is None:
        if folder is None:
            return "Không tìm thấy thư mục phim bộ."
        rows = collect_series_videos(folder)

    total = len(rows)
    if total == 0:
        return "Thư mục phim bộ không có tập video nào."

    with_any_url = [row for row in rows if str(row.get("source_url") or "").strip()]
    allowed = [row for row in with_any_url if share_manager.is_allowed_share_url(str(row.get("source_url") or ""))]

    if allowed:
        return None

    if with_any_url:
        return (
            f"Có {len(with_any_url)}/{total} tập có link nhưng không hợp lệ. "
            "Chỉ hỗ trợ YouTube và Google Drive."
        )

    return (
        f"Không có tập nào chia sẻ được ({total} tập trong thư mục). "
        "Tải tập qua trang Download để lưu link YouTube/Drive, "
        "hoặc sao chép file đã tải bằng Liminal vào thư mục này."
    )
