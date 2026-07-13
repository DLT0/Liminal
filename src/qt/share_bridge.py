"""QML bridge for media share by short code."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, pyqtProperty, pyqtSignal, pyqtSlot

from src import share_manager
from src.metadata_store import resolve_source_url

if TYPE_CHECKING:
    from src.qt.qml_backend import AppBackend

logger = logging.getLogger(__name__)


class ShareBridge(QObject):
    """Exposed to QML as ``shareBridge`` context property."""

    sharedUpdated = pyqtSignal()
    shareCreated = pyqtSignal(str)
    shareError = pyqtSignal(str)
    redeemSuccess = pyqtSignal(str)
    isLoadingChanged = pyqtSignal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._backend: AppBackend | None = None
        self._is_loading = False
        self._refresh_task: asyncio.Task | None = None
        self._action_task: asyncio.Task | None = None

    def set_backend(self, backend: AppBackend) -> None:
        self._backend = backend

    @pyqtProperty(bool, notify=isLoadingChanged)
    def isLoading(self) -> bool:
        return self._is_loading

    def _set_loading(self, loading: bool) -> None:
        if self._is_loading == loading:
            return
        self._is_loading = loading
        self.isLoadingChanged.emit()

    def emit_cached_shared(self) -> None:
        """Push on-disk shared items to the backend without network I/O."""
        cached = share_manager.get_cached_items()
        if cached and self._backend is not None:
            self._backend.apply_shared_items(cached)
            self.sharedUpdated.emit()

    @pyqtSlot()
    def refreshShared(self) -> None:
        cached = share_manager.get_cached_items()
        if cached and self._backend is not None:
            self._backend.apply_shared_items(cached)

        if self._refresh_task and not self._refresh_task.done():
            return

        self._refresh_task = asyncio.create_task(self._refresh())

    async def _refresh(self) -> None:
        self._set_loading(True)
        try:
            items = await share_manager.refresh_shared_items()
            if self._backend is not None:
                self._backend.apply_shared_items(items)
            self.sharedUpdated.emit()
        except asyncio.CancelledError:
            raise
        except ValueError as exc:
            logger.warning("Shared items refresh failed: %s", exc)
            self.shareError.emit(str(exc))
        except Exception:
            logger.exception("Unexpected shared items refresh failure")
            self.shareError.emit("Không thể tải danh sách chia sẻ.")
        finally:
            self._set_loading(False)

    @pyqtSlot(str)
    def redeemCode(self, code: str) -> None:
        value = (code or "").strip()
        if not value:
            self.shareError.emit("Nhập mã chia sẻ.")
            return
        if self._action_task and not self._action_task.done():
            return
        self._action_task = asyncio.create_task(self._redeem(value))

    async def _redeem(self, code: str) -> None:
        self._set_loading(True)
        try:
            item = await share_manager.redeem_share_code(code)
            items = share_manager.get_cached_items()
            if self._backend is not None:
                self._backend.apply_shared_items(items)
                media_type = str(item.get("media_type") or "")
                share_id = str(item.get("id") or "")
                if media_type == "series":
                    self._backend.queueInitialSharedSeriesDownloads(share_id)
                elif media_type == "playlist":
                    self._backend.queueInitialSharedPlaylistDownloads(share_id)
                self._backend.setCurrentPage(share_manager.redeem_target_page(media_type))
            self.redeemSuccess.emit(share_manager.redeem_success_message(item))
            self.sharedUpdated.emit()
        except asyncio.CancelledError:
            raise
        except ValueError as exc:
            self.shareError.emit(str(exc))
        except Exception:
            logger.exception("Redeem share code failed")
            self.shareError.emit("Không thể nhập mã chia sẻ.")
        finally:
            self._set_loading(False)

    @pyqtSlot(str)
    def createShareFromLibraryPath(self, path: str) -> None:
        if self._backend is None:
            self.shareError.emit("Backend chưa sẵn sàng.")
            return
        if self._action_task and not self._action_task.done():
            return
        self._action_task = asyncio.create_task(self._create_share_from_library(path))

    @pyqtSlot(str)
    def createShareFromSeriesPath(self, path: str) -> None:
        if self._backend is None:
            self.shareError.emit("Backend chưa sẵn sàng.")
            return
        if self._action_task and not self._action_task.done():
            return
        self._action_task = asyncio.create_task(self._create_share_from_series(path))

    @pyqtSlot(str)
    def createShareFromPlaylistPath(self, path: str) -> None:
        if self._backend is None:
            self.shareError.emit("Backend chưa sẵn sàng.")
            return
        if self._action_task and not self._action_task.done():
            return
        self._action_task = asyncio.create_task(self._create_share_from_playlist(path))

    @pyqtSlot(str)
    def createShareFromMusicPath(self, path: str) -> None:
        if self._backend is None:
            self.shareError.emit("Backend chưa sẵn sàng.")
            return
        if self._action_task and not self._action_task.done():
            return
        self._action_task = asyncio.create_task(self._create_share_from_music(path))

    async def _create_share_from_library(self, path: str) -> None:
        if self._backend is None:
            return
        self._set_loading(True)
        try:
            info = self._backend.library_share_info(path)
            if info is None:
                raise ValueError("Không thể chia sẻ mục này.")
            source_url = str(info.get("source_url") or "").strip()
            if not source_url:
                raise ValueError(
                    "Không có link gốc (YouTube/Drive). "
                    "Phim cần được tải từ trang Download trước."
                )
            result = await share_manager.create_share(
                title=str(info.get("title") or "Không có tên"),
                author=str(info.get("author") or ""),
                source_url=source_url,
                thumbnail_url=str(info.get("thumbnail_url") or ""),
            )
            self.shareCreated.emit(str(result.get("code") or ""))
        except ValueError as exc:
            self.shareError.emit(str(exc))
        except Exception:
            logger.exception("Create share from library failed")
            self.shareError.emit("Không thể tạo mã chia sẻ.")
        finally:
            self._set_loading(False)

    async def _create_share_from_music(self, path: str) -> None:
        if self._backend is None:
            return
        self._set_loading(True)
        try:
            info = self._backend.library_music_share_info(path)
            if info is None:
                raise ValueError("Không thể chia sẻ bài hát này.")
            source_url = str(info.get("source_url") or "").strip()
            if not source_url:
                raise ValueError(
                    "Không có link gốc (YouTube/Drive). "
                    "Bài hát cần được tải từ trang Download trước."
                )
            result = await share_manager.create_share(
                title=str(info.get("title") or "Không có tên"),
                author=str(info.get("author") or ""),
                source_url=source_url,
                thumbnail_url=str(info.get("thumbnail_url") or ""),
                media_type="music",
            )
            self.shareCreated.emit(str(result.get("code") or ""))
        except ValueError as exc:
            self.shareError.emit(str(exc))
        except Exception:
            logger.exception("Create music share failed")
            self.shareError.emit("Không thể tạo mã chia sẻ bài hát.")
        finally:
            self._set_loading(False)

    async def _create_share_from_series(self, path: str) -> None:
        if self._backend is None:
            return
        self._set_loading(True)
        try:
            from pathlib import Path

            from src.series_layout import collect_series_videos, episode_share_payload, save_series_rows
            from src.series_share import series_share_block_reason, series_share_no_source_message
            from src import share_manager

            info = self._backend.library_series_share_info(path)
            resolved = Path(path)
            try:
                folder = resolved.resolve() if resolved.is_dir() else resolved.parent.resolve()
            except OSError:
                folder = resolved
            rows = collect_series_videos(folder)
            for row in rows:
                path = str(row.get("path") or "").strip()
                if not path:
                    continue
                recovered = resolve_source_url(path, cache=True)
                if recovered:
                    row["source_url"] = recovered
            block_reason = series_share_block_reason(rows)
            if info is None:
                raise ValueError(block_reason or series_share_no_source_message(len(rows)))

            shareable = [
                row for row in rows
                if share_manager.is_allowed_share_url(str(row.get("source_url") or ""))
            ]
            if not shareable:
                raise ValueError(block_reason or series_share_no_source_message(len(rows)))

            title = str(info.get("title") or "Phim bộ")
            try:
                rows = await share_manager.ai_sort_series_episodes(
                    series_title=title,
                    rows=rows,
                )
                save_series_rows(rows)
            except ValueError as exc:
                logger.warning("AI sort before share failed, using local order: %s", exc)

            episodes = [
                episode_share_payload(row)
                for row in rows
                if share_manager.is_allowed_share_url(str(row.get("source_url") or ""))
            ]
            if not episodes:
                raise ValueError(block_reason or series_share_no_source_message(len(rows)))
            result = await share_manager.create_series_share(
                title=title,
                author=str(info.get("author") or ""),
                thumbnail_url=str(info.get("thumbnail_url") or ""),
                episodes=episodes,
            )
            self.shareCreated.emit(str(result.get("code") or ""))
        except ValueError as exc:
            self.shareError.emit(str(exc))
        except Exception:
            logger.exception("Create series share failed")
            self.shareError.emit("Không thể tạo mã chia sẻ phim bộ.")
        finally:
            self._set_loading(False)

    async def _create_share_from_playlist(self, path: str) -> None:
        if self._backend is None:
            return
        self._set_loading(True)
        try:
            from pathlib import Path

            from src import share_manager
            from src.metadata_store import resolve_source_url
            from src.playlist_layout import collect_playlist_tracks, track_share_payload
            from src.playlist_share import playlist_share_block_reason

            if str(path or "").strip().startswith("__liminal__:"):
                raise ValueError("Không thể chia sẻ All Musics.")

            info = self._backend.library_playlist_share_info(path)
            resolved = Path(path)
            try:
                folder = resolved.resolve() if resolved.is_dir() else resolved.parent.resolve()
            except OSError:
                folder = resolved
            rows = collect_playlist_tracks(folder)
            for row in rows:
                track_path = str(row.get("path") or "").strip()
                if not track_path:
                    continue
                recovered = resolve_source_url(track_path, cache=True)
                if recovered:
                    row["source_url"] = recovered
            block_reason = playlist_share_block_reason(rows)
            if info is None:
                raise ValueError(block_reason or "Không thể chia sẻ playlist này.")

            tracks = [
                track_share_payload(row)
                for row in rows
                if share_manager.is_allowed_share_url(str(row.get("source_url") or ""))
            ]
            if not tracks:
                raise ValueError(block_reason or "Không có bài nào có link gốc để chia sẻ.")

            result = await share_manager.create_playlist_share(
                title=str(info.get("title") or "Playlist"),
                author=str(info.get("author") or ""),
                thumbnail_url=str(info.get("thumbnail_url") or ""),
                tracks=tracks,
            )
            self.shareCreated.emit(str(result.get("code") or ""))
        except ValueError as exc:
            self.shareError.emit(str(exc))
        except Exception:
            logger.exception("Create playlist share failed")
            self.shareError.emit("Không thể tạo mã chia sẻ playlist.")
        finally:
            self._set_loading(False)

    @pyqtSlot(int)
    def dismissSharedItem(self, index: int) -> None:
        if self._backend is None:
            return
        self._backend.dismissSharedItem(index)
