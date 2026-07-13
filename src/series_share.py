"""Helpers for validating series share readiness."""

from __future__ import annotations

from pathlib import Path

from src import share_manager
from src.series_layout import collect_series_videos


def _episode_label(count: int) -> str:
    if count == 1:
        return "tập phim"
    return f"{count} tập phim"


def series_share_no_source_message(total: int) -> str:
    """Message when no episode has a YouTube/Drive source link."""
    label = _episode_label(total)
    if total == 1:
        return (
            "Không thể chia sẻ phim bộ này.\n\n"
            "Tập phim chưa có liên kết YouTube hoặc Google Drive. "
            "Chia sẻ chỉ khả dụng với nội dung được tải qua Liminal (mục Download), "
            "vì ứng dụng cần lưu liên kết nguồn gốc khi tải xong.\n\n"
            "Nếu bạn thêm file thủ công vào thư mục, hãy tải lại qua Liminal "
            "để có thể chia sẻ."
        )
    return (
        "Không thể chia sẻ phim bộ này.\n\n"
        f"Cả {label} trong thư mục đều chưa có liên kết YouTube hoặc Google Drive. "
        "Chia sẻ chỉ khả dụng với nội dung được tải qua Liminal (mục Download), "
        "vì ứng dụng cần lưu liên kết nguồn gốc khi tải xong.\n\n"
        "Nếu bạn thêm file thủ công vào thư mục, hãy tải lại các tập qua Liminal "
        "để có thể chia sẻ."
    )


def series_share_invalid_source_message(invalid_count: int, total: int) -> str:
    """Message when episodes have source URLs that are not YouTube/Drive."""
    return (
        "Không thể chia sẻ phim bộ này.\n\n"
        f"{invalid_count}/{total} tập có liên kết nguồn nhưng không thuộc YouTube hoặc Google Drive. "
        "Liminal chỉ hỗ trợ chia sẻ nội dung từ hai nền tảng này.\n\n"
        "Hãy tải lại các tập qua mục Download để lưu liên kết hợp lệ."
    )


def series_share_block_reason(rows: list[dict] | None = None, *, folder: Path | None = None) -> str | None:
    """Return a user-facing error when a series folder cannot be shared."""
    if rows is None:
        if folder is None:
            return "Không tìm thấy thư mục phim bộ."
        rows = collect_series_videos(folder)

    total = len(rows)
    if total == 0:
        return (
            "Không thể chia sẻ phim bộ này.\n\n"
            "Thư mục chưa có tập video nào. Hãy thêm ít nhất một tập trước khi chia sẻ."
        )

    with_any_url = [row for row in rows if str(row.get("source_url") or "").strip()]
    allowed = [row for row in with_any_url if share_manager.is_allowed_share_url(str(row.get("source_url") or ""))]

    if allowed:
        return None

    if with_any_url:
        return series_share_invalid_source_message(len(with_any_url), total)

    return series_share_no_source_message(total)
