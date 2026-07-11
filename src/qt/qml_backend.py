"""QML ↔ Python bridge for Liminal."""

from __future__ import annotations

import logging
import random
import asyncio
import re
import threading
from pathlib import Path

from PyQt6.QtCore import (
    QAbstractListModel,
    QModelIndex,
    QObject,
    Qt,
    QTimer,
    QUrl,
    pyqtProperty,
    pyqtSignal,
    pyqtSlot,
)
from PyQt6.QtGui import QDesktopServices, QGuiApplication
from PyQt6.QtWidgets import QApplication, QFileDialog

from src.config import AUDIO_EXTS
from src.downloader import Downloader, DownloadFailed
from src.models import MediaInfo, PlaybackStatus
from src.player import PlayerBridge
from src.scanner import scan_music, scan_playlist, scan_video
from src.settings_store import load_raw_settings, load_settings, save_raw_settings, save_settings

logger = logging.getLogger(__name__)

APP_ICON_PATH = Path(__file__).resolve().parent / "liminal.png"

ACCENT_COLORS = [
    "#4facfe",
    "#a855f7",
    "#38e6ff",
    "#7850ff",
    "#6366f1",
]


def _is_remote(path: str) -> bool:
    return path.startswith(("http://", "https://"))


def _media_item(info: MediaInfo, index: int, *, audio_only: bool = True) -> dict:
    return {
        "title": info.title,
        "subtitle": info.artist or ("Music" if audio_only else "Video"),
        "path": info.path,
        "url": info.url or info.path,
        "track_id": info.track_id or info.url or info.path,
        "duration": info.duration,
        "image": "",
        "accent": ACCENT_COLORS[index % len(ACCENT_COLORS)],
        "audio_only": audio_only,
        "is_remote": _is_remote(info.path or info.url),
        "download_percent": 0.0,
        "download_status": "",
        "is_downloading": False,
    }


class MediaListModel(QAbstractListModel):
    """List model for GridView media cards."""

    TitleRole = Qt.ItemDataRole.UserRole + 1
    SubtitleRole = Qt.ItemDataRole.UserRole + 2
    ImageSourceRole = Qt.ItemDataRole.UserRole + 3
    AccentColorRole = Qt.ItemDataRole.UserRole + 4
    PathRole = Qt.ItemDataRole.UserRole + 5
    AudioOnlyRole = Qt.ItemDataRole.UserRole + 6
    UrlRole = Qt.ItemDataRole.UserRole + 7
    DurationRole = Qt.ItemDataRole.UserRole + 8
    TrackIdRole = Qt.ItemDataRole.UserRole + 9
    IsRemoteRole = Qt.ItemDataRole.UserRole + 10
    DownloadPercentRole = Qt.ItemDataRole.UserRole + 11
    DownloadStatusRole = Qt.ItemDataRole.UserRole + 12
    IsDownloadingRole = Qt.ItemDataRole.UserRole + 13

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._items: list[dict] = []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._items)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self._items):
            return None
        item = self._items[index.row()]
        role_map = {
            self.TitleRole: "title",
            self.SubtitleRole: "subtitle",
            self.ImageSourceRole: "image",
            self.AccentColorRole: "accent",
            self.PathRole: "path",
            self.AudioOnlyRole: "audio_only",
            self.UrlRole: "url",
            self.DurationRole: "duration",
            self.TrackIdRole: "track_id",
            self.IsRemoteRole: "is_remote",
            self.DownloadPercentRole: "download_percent",
            self.DownloadStatusRole: "download_status",
            self.IsDownloadingRole: "is_downloading",
        }
        key = role_map.get(role)
        if key is None:
            return None
        value = item.get(key, "")
        if role == self.AccentColorRole and not value:
            return ACCENT_COLORS[0]
        if role in (self.AudioOnlyRole, self.IsRemoteRole, self.IsDownloadingRole):
            return bool(value)
        if role == self.DownloadPercentRole:
            return float(value or 0.0)
        return value

    def roleNames(self) -> dict[int, bytes]:
        return {
            self.TitleRole: b"title",
            self.SubtitleRole: b"subtitle",
            self.ImageSourceRole: b"imageSource",
            self.AccentColorRole: b"accentColor",
            self.PathRole: b"path",
            self.AudioOnlyRole: b"audioOnly",
            self.UrlRole: b"url",
            self.DurationRole: b"duration",
            self.TrackIdRole: b"trackId",
            self.IsRemoteRole: b"isRemote",
            self.DownloadPercentRole: b"downloadPercent",
            self.DownloadStatusRole: b"downloadStatus",
            self.IsDownloadingRole: b"isDownloading",
        }

    def set_items(self, items: list[dict]) -> None:
        self.beginResetModel()
        self._items = items
        self.endResetModel()

    def item_at(self, row: int) -> dict | None:
        if 0 <= row < len(self._items):
            return self._items[row]
        return None

    def update_download_state(
        self,
        track_id: str,
        *,
        percent: float | None = None,
        status: str | None = None,
        is_downloading: bool | None = None,
    ) -> None:
        for row, item in enumerate(self._items):
            if item.get("track_id") != track_id:
                continue
            if percent is not None:
                item["download_percent"] = percent
            if status is not None:
                item["download_status"] = status
            if is_downloading is not None:
                item["is_downloading"] = is_downloading
            idx = self.index(row, 0)
            self.dataChanged.emit(
                idx,
                idx,
                [
                    self.DownloadPercentRole,
                    self.DownloadStatusRole,
                    self.IsDownloadingRole,
                ],
            )
            break


class AppBackend(QObject):
    """Exposed to QML as ``backend`` context property."""

    trackTitleChanged = pyqtSignal()
    trackArtistChanged = pyqtSignal()
    isPlayingChanged = pyqtSignal()
    volumeChanged = pyqtSignal()
    currentPageChanged = pyqtSignal()
    positionChanged = pyqtSignal()
    durationChanged = pyqtSignal()
    shuffleChanged = pyqtSignal()
    loopChanged = pyqtSignal()
    mutedChanged = pyqtSignal()
    hasMediaChanged = pyqtSignal()
    discoverResultsReady = pyqtSignal(object)
    mediaRootChanged = pyqtSignal()
    musicDirChanged = pyqtSignal()
    videoDirChanged = pyqtSignal()
    playlistDirChanged = pyqtSignal()
    settingsSavedChanged = pyqtSignal()
    themeIndexChanged = pyqtSignal()
    pageTitleChanged = pyqtSignal()
    downloadQualityChanged = pyqtSignal()
    ytDlpUpdateStatusChanged = pyqtSignal()
    searchResults = pyqtSignal(list)
    searchError = pyqtSignal(str)
    downloadProgress = pyqtSignal(str, float)
    downloadFinished = pyqtSignal(str)
    downloadError = pyqtSignal(str)

    def __init__(self, player: PlayerBridge, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._player = player
        self._track_title = "LIMINAL"
        self._track_artist = "Offline Media Player"
        self._is_playing = False
        self._volume = 100
        self._current_page: int = 1
        self._page_title = "Playlist"
        self._filter = ""
        self._app_icon_url = QUrl.fromLocalFile(str(APP_ICON_PATH.resolve())).toString()

        settings = load_settings()
        self._media_root = settings["media_root"]
        self._music_dir = settings["music_dir"]
        self._video_dir = settings["video_dir"]
        self._playlist_dir = settings["playlist_dir"]
        self._search_seq = 0
        self._settings_saved = True
        self.downloader = Downloader(
            Path(self._music_dir),
            Path(self._video_dir),
        )

        raw = load_raw_settings()
        self._theme_index: int = int(raw.get("theme_index", 0))
        self._download_quality: str = str(raw.get("download_quality", "1080"))
        self._yt_dlp_update_status: str = ""

        self._music_paths = [info.path for info in scan_music()]
        self._current_path = ""
        self._current_audio_only = True
        self._shuffle_on = False
        self._loop_on = False
        self._muted = False
        self._volume_before_mute = 100
        self._position = 0.0
        self._duration = 0.0
        self._has_media = False
        self._media_music_preview: list[dict] = []
        self._media_video_preview: list[dict] = []

        self._all_music_items: list[dict] = []
        self._all_video_items: list[dict] = []
        self._all_playlist_items: list[dict] = []

        self._music_model = MediaListModel(self)
        self._video_model = MediaListModel(self)
        self._playlist_model = MediaListModel(self)
        self._media_music_model = MediaListModel(self)
        self._media_video_model = MediaListModel(self)

        self._load_libraries()

        self._player.state_changed.connect(self._on_state_changed)
        self._player.position_changed.connect(self._on_position_changed)
        self._player.track_ended.connect(self._on_track_ended)

    # ── Properties ──

    @pyqtProperty(str, constant=True)
    def appIconUrl(self) -> str:
        return self._app_icon_url

    @pyqtProperty(QObject, constant=True)
    def musicModel(self) -> MediaListModel:
        return self._music_model

    @pyqtProperty(QObject, constant=True)
    def videoModel(self) -> MediaListModel:
        return self._video_model

    @pyqtProperty(QObject, constant=True)
    def playlistModel(self) -> MediaListModel:
        return self._playlist_model

    @pyqtProperty(QObject, constant=True)
    def mediaMusicModel(self) -> MediaListModel:
        return self._media_music_model

    @pyqtProperty(QObject, constant=True)
    def mediaVideoModel(self) -> MediaListModel:
        return self._media_video_model

    @pyqtProperty(str, notify=trackTitleChanged)
    def trackTitle(self) -> str:
        return self._track_title

    @pyqtProperty(str, notify=trackArtistChanged)
    def trackArtist(self) -> str:
        return self._track_artist

    @pyqtProperty(bool, notify=isPlayingChanged)
    def isPlaying(self) -> bool:
        return self._is_playing

    @pyqtProperty(int, notify=volumeChanged)
    def volume(self) -> int:
        return self._volume

    @pyqtProperty(int, notify=currentPageChanged)
    def currentPage(self) -> int:
        return self._current_page

    @pyqtProperty(str, notify=pageTitleChanged)
    def pageTitle(self) -> str:
        return self._page_title

    @pyqtProperty(float, notify=positionChanged)
    def position(self) -> float:
        return self._position

    @pyqtProperty(float, notify=durationChanged)
    def duration(self) -> float:
        return self._duration

    @pyqtProperty(bool, notify=shuffleChanged)
    def shuffleOn(self) -> bool:
        return self._shuffle_on

    @pyqtProperty(bool, notify=loopChanged)
    def loopOn(self) -> bool:
        return self._loop_on

    @pyqtProperty(bool, notify=mutedChanged)
    def muted(self) -> bool:
        return self._muted

    @pyqtProperty(bool, notify=hasMediaChanged)
    def hasMedia(self) -> bool:
        return self._has_media

    @pyqtProperty(str, notify=mediaRootChanged)
    def mediaRoot(self) -> str:
        return self._media_root

    @pyqtProperty(str, notify=musicDirChanged)
    def musicDir(self) -> str:
        return self._music_dir

    @pyqtProperty(str, notify=videoDirChanged)
    def videoDir(self) -> str:
        return self._video_dir

    @pyqtProperty(str, notify=playlistDirChanged)
    def playlistDir(self) -> str:
        return self._playlist_dir

    @pyqtProperty(bool, notify=settingsSavedChanged)
    def settingsSaved(self) -> bool:
        return self._settings_saved

    @pyqtProperty(int, notify=themeIndexChanged)
    def themeIndex(self) -> int:
        return self._theme_index

    @pyqtProperty(str, notify=downloadQualityChanged)
    def downloadQuality(self) -> str:
        return self._download_quality

    @pyqtProperty(str, notify=ytDlpUpdateStatusChanged)
    def ytDlpUpdateStatus(self) -> str:
        return self._yt_dlp_update_status

    # ── Slots ──

    @pyqtSlot(int)
    def setCurrentPage(self, page: int) -> None:
        if page in {1, 2, 3}:
            # Also refresh when the user clicks the already-selected tab.
            self._load_libraries()
        if self._current_page != page:
            self._current_page = page
            titles = {
                1: "Playlist",
                2: "Music",
                3: "Videos",
                4: "Download",
                5: "Settings",
            }
            self._page_title = titles.get(page, "Liminal")
            self.pageTitleChanged.emit()
            self.currentPageChanged.emit()

    @pyqtSlot(str)
    def setSearchFilter(self, text: str) -> None:
        self._filter = text.strip().lower()
        if self._current_page == 2:
            self._apply_library_filter(self._all_music_items, self.musicModel)
        elif self._current_page == 3:
            self._apply_library_filter(self._all_video_items, self.videoModel)
        elif self._current_page == 1:
            self._apply_library_filter(self._all_playlist_items, self.playlistModel)

    @pyqtSlot(int)
    def playMedia(self, index: int) -> None:
        model = self._model_for_page(self._current_page)
        item = model.item_at(index)
        if item is None:
            return
        self._play_item(item)

    @pyqtSlot(str)
    def copyToClipboard(self, text: str) -> None:
        value = text.strip()
        if value:
            QGuiApplication.clipboard().setText(value)

    @pyqtSlot()
    def refreshLibraries(self) -> None:
        self._load_libraries()

    @pyqtSlot()
    def rescanLibrary(self) -> None:
        """Rescan local media after a download completes."""
        self._load_libraries()

    @pyqtSlot(str)
    def searchOnline(self, query: str) -> None:
        """Start an online search without blocking Qt's event loop."""
        self._search_seq += 1
        asyncio.create_task(self._search(query, self._search_seq))

    async def _search(self, query: str, seq: int) -> None:
        query = query.strip()
        if not query:
            if seq == self._search_seq:
                self.searchResults.emit([])
            return
        try:
            results = await self.downloader.search(query)
        except DownloadFailed as exc:
            logger.exception("Online search failed for %r", query)
            if seq == self._search_seq:
                self.searchError.emit(str(exc))
            return
        if seq == self._search_seq:
            self.searchResults.emit(list(results or []))

    @pyqtSlot(str, str)
    def downloadMedia(self, url: str, kind: str) -> None:
        """Start an audio/video download without blocking QML."""
        if not re.match(r"^https?://.+", url.strip(), re.IGNORECASE):
            self.downloadError.emit("URL không hợp lệ")
            return
        asyncio.create_task(self._download(url, kind))

    async def _download(self, url: str, kind: str) -> None:
        def hook(data: dict) -> None:
            if data.get("status") != "downloading":
                return
            percent = data.get("_percent_str", "0%")
            try:
                percent_value = float(str(percent).strip().rstrip("%") or 0)
            except ValueError:
                percent_value = 0.0
            filename = str(data.get("filename", ""))
            self.downloadProgress.emit(filename, percent_value)

        if kind not in {"audio", "video"}:
            logger.warning("Ignoring download with unsupported kind: %r", kind)
            return
        try:
            if kind == "audio":
                await self.downloader.download_audio(
                    url,
                    hook,
                )
            else:
                await self.downloader.download_video(
                    url,
                    hook,
                    quality=self._download_quality,
                )
        except DownloadFailed as exc:
            logger.exception("Media download failed for %r", url)
            self.downloadError.emit(str(exc))
            return

        self.downloadFinished.emit(kind)
        self.rescanLibrary()

    @pyqtSlot(int)
    def setThemeIndex(self, index: int) -> None:
        if self._theme_index != index:
            self._theme_index = index
            self.themeIndexChanged.emit()
            save_raw_settings({"theme_index": index})

    @pyqtSlot(str)
    def setDownloadQuality(self, quality: str) -> None:
        if self._download_quality != quality:
            self._download_quality = quality
            self.downloadQualityChanged.emit()
            save_raw_settings({"download_quality": quality})

    @pyqtSlot()
    def updateYtDlp(self) -> None:
        if self._yt_dlp_update_status == "Đang cập nhật...":
            return
            
        self._yt_dlp_update_status = "Đang cập nhật..."
        self.ytDlpUpdateStatusChanged.emit()

        import asyncio
        loop = asyncio.get_running_loop()
        
        def _run_update():
            import sys
            import subprocess
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-U", "yt-dlp"],
                    capture_output=True, text=True, check=True
                )
                if "Requirement already satisfied" in result.stdout and "yt-dlp" in result.stdout:
                     return "yt-dlp đã ở phiên bản mới nhất."
                return "Cập nhật yt-dlp thành công!"
            except subprocess.CalledProcessError as e:
                return f"Lỗi cập nhật: {e.stderr}"
            except Exception as e:
                return f"Lỗi: {str(e)}"
                
        def _on_done(future):
            self._yt_dlp_update_status = future.result()
            self.ytDlpUpdateStatusChanged.emit()
            
        task = loop.run_in_executor(None, _run_update)
        asyncio.ensure_future(task).add_done_callback(_on_done)

    def _apply_storage_settings(self, settings: dict[str, str]) -> None:
        self._media_root = settings["media_root"]
        self._music_dir = settings["music_dir"]
        self._video_dir = settings["video_dir"]
        self._playlist_dir = settings["playlist_dir"]
        self.downloader.music_dir = Path(self._music_dir)
        self.downloader.video_dir = Path(self._video_dir)
        self.mediaRootChanged.emit()
        self.musicDirChanged.emit()
        self.videoDirChanged.emit()
        self.playlistDirChanged.emit()

    @pyqtSlot(result=str)
    def pickMediaRoot(self) -> str:
        parent = QApplication.activeWindow()
        chosen = QFileDialog.getExistingDirectory(
            parent,
            "Chọn thư mục lưu trữ media",
            self._media_root,
        )
        if not chosen:
            return ""
        settings = save_settings(chosen)
        self._apply_storage_settings(settings)
        self._settings_saved = True
        self.settingsSavedChanged.emit()
        self._load_libraries()
        return chosen

    @pyqtSlot()
    def saveSettings(self) -> None:
        settings = save_settings(self._media_root)
        self._apply_storage_settings(settings)
        self._settings_saved = True
        self.settingsSavedChanged.emit()
        self._load_libraries()

    @pyqtSlot(int)
    def playMediaMusic(self, index: int) -> None:
        item = self.mediaMusicModel.item_at(index)
        if item is not None:
            self._play_item(item)

    @pyqtSlot(int)
    def playMediaVideo(self, index: int) -> None:
        item = self.mediaVideoModel.item_at(index)
        if item is not None:
            self._play_item(item)

    @pyqtSlot()
    def openMusicPage(self) -> None:
        self.setCurrentPage(2)

    @pyqtSlot()
    def openVideosPage(self) -> None:
        self.setCurrentPage(3)

    @pyqtSlot()
    def togglePause(self) -> None:
        self._player.toggle_pause()

    @pyqtSlot()
    def previous(self) -> None:
        if self._current_audio_only and self._current_path:
            self._play_adjacent(-1)
        else:
            self._player.seek(-10)

    @pyqtSlot()
    def next(self) -> None:
        if self._current_audio_only and self._current_path:
            self._play_adjacent(1)
        else:
            self._player.seek(10)

    @pyqtSlot(int)
    def setVolume(self, vol: int) -> None:
        vol = max(0, min(100, vol))
        if vol > 0 and self._muted:
            self._muted = False
            self.mutedChanged.emit()
        self._player.set_volume(vol)

    @pyqtSlot()
    def toggleMute(self) -> None:
        if self._muted:
            self._muted = False
            self._player.set_volume(self._volume_before_mute or 100)
        else:
            self._volume_before_mute = self._volume
            self._muted = True
            self._player.set_volume(0)
        self.mutedChanged.emit()

    @pyqtSlot()
    def toggleShuffle(self) -> None:
        self._shuffle_on = not self._shuffle_on
        self.shuffleChanged.emit()

    @pyqtSlot()
    def toggleLoop(self) -> None:
        self._loop_on = not self._loop_on
        self.loopChanged.emit()

    @pyqtSlot(float)
    def seekTo(self, position: float) -> None:
        self._player.seek_absolute(max(0.0, position))

    # ── Internal ──

    def _model_for_page(self, page: int) -> MediaListModel:
        return {
            1: self.playlistModel,
            2: self.musicModel,
            3: self.videoModel,
        }.get(page, self.playlistModel)

    def _target_dir(self, target: str) -> Path:
        if target == "music":
            return Path(self._music_dir)
        if target == "video":
            return Path(self._video_dir)
        return Path(self._playlist_dir)

    def _load_libraries(self) -> None:
        self._music_paths = [info.path for info in scan_music()]
        self._all_music_items = [
            _media_item(info, i, audio_only=True) for i, info in enumerate(scan_music())
        ]
        self._all_video_items = [
            _media_item(info, i, audio_only=False) for i, info in enumerate(scan_video())
        ]
        # Playlist is the unified media view: include explicitly playlisted
        # files as well as downloaded Music/Videos, without duplicate paths.
        self._all_playlist_items = []
        playlist_infos = scan_playlist() + scan_music() + scan_video()
        seen_playlist_paths: set[str] = set()
        for info in playlist_infos:
            if info.path in seen_playlist_paths:
                continue
            seen_playlist_paths.add(info.path)
            audio_only = Path(info.path).suffix.lower() in AUDIO_EXTS
            self._all_playlist_items.append(
                _media_item(info, len(self._all_playlist_items), audio_only=audio_only)
            )

        self._apply_library_filter(self._all_music_items, self.musicModel)
        self._apply_library_filter(self._all_video_items, self.videoModel)
        self._apply_library_filter(self._all_playlist_items, self.playlistModel)

        preview_limit = 12
        self._media_music_preview = self._all_music_items[:preview_limit]
        self._media_video_preview = self._all_video_items[:preview_limit]
        self.mediaMusicModel.set_items(self._media_music_preview)
        self.mediaVideoModel.set_items(self._media_video_preview)

    def _apply_library_filter(self, source: list[dict], model: MediaListModel) -> None:
        q = self._filter
        if not q:
            model.set_items(source)
            return
        model.set_items(
            [
                item
                for item in source
                if q in item["title"].lower() or q in item["subtitle"].lower()
            ]
        )

    def _play_item(self, item: dict) -> None:
        path = item.get("path") or item.get("url") or ""
        if not path:
            return
        audio_only = item.get("audio_only", True)
        title = item.get("title", "")
        artist = item.get("subtitle", "")

        if _is_remote(path):
            if not self._is_online:
                return
            self._current_path = path
            self._current_audio_only = audio_only
            self._player.play(path, audio_only=audio_only, title=title, artist=artist)
            return

        self._current_path = path
        self._current_audio_only = audio_only
        self._player.play(path, audio_only=audio_only, title=title, artist=artist)

    def _music_index(self) -> int:
        if not self._current_path:
            return -1
        try:
            return self._music_paths.index(self._current_path)
        except ValueError:
            return -1

    def _play_path(self, path: str) -> None:
        self._current_path = path
        self._current_audio_only = True
        self._player.play(path, audio_only=True)

    def _play_adjacent(self, delta: int) -> None:
        if not self._music_paths:
            return

        idx = self._music_index()
        if idx < 0:
            idx = 0
        elif delta > 0:
            next_idx = idx + 1
            if next_idx >= len(self._music_paths):
                if self._loop_on:
                    next_idx = 0
                else:
                    return
            idx = next_idx
        else:
            idx = (idx - 1) % len(self._music_paths)

        self._play_path(self._music_paths[idx])

    def _play_random_other(self) -> None:
        if len(self._music_paths) <= 1:
            if self._loop_on and self._music_paths:
                self._play_path(self._music_paths[0])
            return

        candidates = [p for p in self._music_paths if p != self._current_path]
        if candidates:
            self._play_path(random.choice(candidates))

    def _on_track_ended(self) -> None:
        if not self._current_audio_only or not self._current_path:
            return
        if _is_remote(self._current_path):
            return
        if self._shuffle_on:
            self._play_random_other()
        else:
            self._play_adjacent(1)

    def _on_state_changed(self, state) -> None:
        if state.path:
            self._current_path = state.path
            self._current_audio_only = (
                state.path in self._music_paths or _is_remote(state.path)
            )

        if state.title and state.title != "Nothing playing":
            self._track_title = state.title[:40]
            self._track_artist = (
                f"•  {state.artist}" if state.artist != "—" else "Offline Media Player"
            )
        else:
            self._track_title = "LIMINAL"
            self._track_artist = "Offline Media Player"

        playing = state.status == PlaybackStatus.PLAYING
        if self._is_playing != playing:
            self._is_playing = playing
            self.isPlayingChanged.emit()

        has_media = state.status != PlaybackStatus.STOPPED
        if self._has_media != has_media:
            self._has_media = has_media
            self.hasMediaChanged.emit()

        if state.status == PlaybackStatus.STOPPED:
            if self._position != 0.0:
                self._position = 0.0
                self.positionChanged.emit()
            if self._duration != 0.0:
                self._duration = 0.0
                self.durationChanged.emit()

        if self._volume != state.volume:
            self._volume = state.volume
            self.volumeChanged.emit()
            if state.volume == 0 and not self._muted:
                self._muted = True
                self.mutedChanged.emit()
            elif state.volume > 0 and self._muted:
                self._muted = False
                self.mutedChanged.emit()

        self.trackTitleChanged.emit()
        self.trackArtistChanged.emit()

    def _on_position_changed(self, time_pos: float, duration: float) -> None:
        if self._position != time_pos:
            self._position = time_pos
            self.positionChanged.emit()
        if self._duration != duration:
            self._duration = duration
            self.durationChanged.emit()

    def cleanup(self) -> None:
        self._player.cleanup_sync()
