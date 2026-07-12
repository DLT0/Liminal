"""QML bridge for the Discover feed."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, pyqtProperty, pyqtSignal, pyqtSlot

from src import discover_manager

if TYPE_CHECKING:
    from src.qt.qml_backend import AppBackend

logger = logging.getLogger(__name__)


class DiscoverBridge(QObject):
    """Exposed to QML as ``discoverBridge`` context property."""

    feedUpdated = pyqtSignal(list)
    feedError = pyqtSignal(str)
    isLoadingChanged = pyqtSignal()
    downloadRequested = pyqtSignal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._backend: AppBackend | None = None
        self._is_loading = False
        self._items: list[dict] = []
        self._refresh_task: asyncio.Task | None = None

    def set_backend(self, backend: AppBackend) -> None:
        self._backend = backend

    @pyqtProperty(bool, notify=isLoadingChanged)
    def isLoading(self) -> bool:
        return self._is_loading

    @pyqtProperty(bool, constant=True)
    def hasCachedFeed(self) -> bool:
        return bool(discover_manager.get_cached_feed())

    def _set_loading(self, loading: bool) -> None:
        if self._is_loading == loading:
            return
        self._is_loading = loading
        self.isLoadingChanged.emit()

    def _annotate_items(self, items: list[dict]) -> list[dict]:
        if self._backend is None:
            return items
        return self._backend.annotate_discover_items(items)

    def _emit_feed(self, items: list[dict]) -> None:
        self._items = items
        self.feedUpdated.emit(self._annotate_items(items))

    def emit_cached_feed(self) -> None:
        """Push the on-disk cache to QML without network I/O."""
        cached = discover_manager.get_cached_feed()
        if cached:
            self._emit_feed(cached)

    def lookup_item(self, item_id: str) -> dict | None:
        needle = (item_id or "").strip()
        if not needle:
            return None
        for item in self._items:
            if str(item.get("id") or "").strip() == needle:
                return item
        for item in discover_manager.get_cached_feed():
            if str(item.get("id") or "").strip() == needle:
                return item
        return None

    @pyqtSlot()
    @pyqtSlot(bool)
    def refreshFeed(self, force: bool = False) -> None:
        """Return cached feed immediately, then refetch when stale or forced."""
        cached = discover_manager.get_cached_feed()
        if cached:
            self._emit_feed(cached)

        if not force and cached and not discover_manager.cache_is_stale(force=False):
            return

        if self._refresh_task and not self._refresh_task.done():
            if not force:
                return
            self._refresh_task.cancel()

        self._refresh_task = asyncio.create_task(self._refresh(force=force))

    async def _refresh(self, *, force: bool) -> None:
        self._set_loading(True)
        try:
            items = await discover_manager.fetch_discover_feed()
            self._emit_feed(items)
        except asyncio.CancelledError:
            raise
        except ValueError as exc:
            logger.warning("Discover feed refresh failed: %s", exc)
            self.feedError.emit(str(exc))
            cached = discover_manager.get_cached_feed()
            if cached:
                self._emit_feed(cached)
        except Exception as exc:
            logger.exception("Unexpected discover feed refresh failure")
            self.feedError.emit("Không thể tải nội dung Discover.")
            cached = discover_manager.get_cached_feed()
            if cached:
                self._emit_feed(cached)
        finally:
            self._set_loading(False)

    @pyqtSlot(str)
    def downloadItem(self, item_id: str) -> None:
        """Enqueue a discover item through the existing download pipeline."""
        if self._backend is None:
            self.feedError.emit("Backend chưa sẵn sàng.")
            return

        item = self.lookup_item(item_id)
        if item is None:
            self.feedError.emit("Không tìm thấy mục Discover.")
            return

        source_url = str(item.get("source_url") or item.get("url") or "").strip()
        if not source_url:
            self.feedError.emit("Mục Discover thiếu source_url.")
            return

        media_type = str(item.get("media_type") or "video").strip().lower()
        kind = "music" if media_type == "music" else "video"
        self._backend.downloadMedia(source_url, kind, "")
        self.downloadRequested.emit(item_id)
