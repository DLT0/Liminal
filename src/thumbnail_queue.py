"""Background thumbnail extraction for library cards."""

from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable

from PyQt6.QtCore import QObject, pyqtSignal

from src.metadata_store import read_embedded_metadata, read_video_thumbnail

logger = logging.getLogger(__name__)

_MAX_WORKERS = min(4, max(2, (os.cpu_count() or 2)))


class ThumbnailQueue(QObject):
    """Extract missing covers/thumbnails off the UI thread."""

    thumbnailReady = pyqtSignal(str, str, bool)

    def __init__(self) -> None:
        super().__init__()
        self._executor = ThreadPoolExecutor(
            max_workers=_MAX_WORKERS,
            thread_name_prefix="liminal-thumb",
        )
        self._pending: set[str] = set()

    def submit(
        self,
        path: str,
        *,
        is_video: bool,
        callback: Callable[[str, str], None] | None = None,
    ) -> None:
        key = path.strip()
        if not key or key in self._pending:
            return
        self._pending.add(key)

        def work() -> str:
            try:
                media_path = Path(key)
                if is_video:
                    return read_video_thumbnail(media_path, extract=True)
                return read_embedded_metadata(media_path, include_cover=True).get("image", "")
            except Exception:
                logger.debug("thumbnail extraction failed for %s", key, exc_info=True)
                return ""
            finally:
                self._pending.discard(key)

        future = self._executor.submit(work)

        def done(future_result) -> None:
            try:
                image = future_result.result()
            except Exception:
                image = ""
            if image:
                self.thumbnailReady.emit(key, image, False)
                if callback is not None:
                    callback(key, image)

        future.add_done_callback(done)

    def submit_folder_preview(
        self,
        path: str,
        callback: Callable[[str, str], None] | None = None,
    ) -> None:
        key = path.strip()
        if not key or key in self._pending:
            return
        self._pending.add(key)

        def work() -> str:
            try:
                from src.scanner import find_folder_preview_image

                return find_folder_preview_image(Path(key), fast=False)
            except Exception:
                logger.debug("folder preview failed for %s", key, exc_info=True)
                return ""
            finally:
                self._pending.discard(key)

        future = self._executor.submit(work)

        def done(future_result) -> None:
            try:
                image = future_result.result()
            except Exception:
                image = ""
            if image:
                self.thumbnailReady.emit(key, image, True)
                if callback is not None:
                    callback(key, image)

        future.add_done_callback(done)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)


_queue: ThumbnailQueue | None = None


def get_thumbnail_queue() -> ThumbnailQueue:
    global _queue
    if _queue is None:
        _queue = ThumbnailQueue()
    return _queue
