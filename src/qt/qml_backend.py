"""QML ↔ Python bridge for Liminal."""

from __future__ import annotations

import logging
import random
import asyncio
import shutil
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

from src.config import AUDIO_EXTS, VIDEO_EXTS
from src.downloader import Downloader, DownloadFailed
from src.folder_order import write_order
from src.metadata_store import delete_metadata, set_cover_image, set_metadata
from src.models import MediaInfo, MediaKind, PlaybackStatus
from src.player import PlayerBridge
from src.scanner import find_folder_preview_image, scan_directory, scan_library_folder
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

NAV_TAB_PAGES = [2, 3, 4, 5]


def _is_remote(path: str) -> bool:
    return path.startswith(("http://", "https://"))


def _media_item(info: MediaInfo, index: int, *, audio_only: bool = True) -> dict:
    is_collection = info.kind in (MediaKind.ALBUM, MediaKind.VIDEO_PLAYLIST, MediaKind.FOLDER)
    if is_collection:
        audio_only = info.kind in (MediaKind.ALBUM, MediaKind.FOLDER)
    return {
        "title": info.title,
        "subtitle": info.artist or ("Music" if audio_only else "Video"),
        "path": info.path,
        "url": info.url or info.path,
        "track_id": info.track_id or info.url or info.path,
        "duration": info.duration,
        "image": info.image or "",
        "accent": ACCENT_COLORS[index % len(ACCENT_COLORS)],
        "audio_only": audio_only,
        "is_remote": _is_remote(info.path or info.url),
        "is_collection": is_collection,
        "kind": info.kind.name.lower(),
        "child_count": info.child_count,
        "preview_images": list(info.preview_images) if is_collection else [],
        "download_percent": 0.0,
        "download_status": "",
        "is_downloading": False,
    }


class MediaListModel(QAbstractListModel):
    """List model for GridView media cards."""

    countChanged = pyqtSignal()

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
    IsCollectionRole = Qt.ItemDataRole.UserRole + 14
    KindRole = Qt.ItemDataRole.UserRole + 15
    ChildCountRole = Qt.ItemDataRole.UserRole + 16
    TrackThumbnailsRole = Qt.ItemDataRole.UserRole + 17

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._items: list[dict] = []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._items)

    @pyqtProperty(int, notify=countChanged)
    def count(self) -> int:
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
            self.IsCollectionRole: "is_collection",
            self.KindRole: "kind",
            self.ChildCountRole: "child_count",
            self.TrackThumbnailsRole: "preview_images",
        }
        key = role_map.get(role)
        if key is None:
            return None
        value = item.get(key, "")
        if role == self.AccentColorRole and not value:
            return ACCENT_COLORS[0]
        if role in (self.AudioOnlyRole, self.IsRemoteRole, self.IsDownloadingRole, self.IsCollectionRole):
            return bool(value)
        if role == self.ChildCountRole:
            return int(value or 0)
        if role == self.TrackThumbnailsRole:
            return list(value or [])
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
            self.IsCollectionRole: b"isCollection",
            self.KindRole: b"kind",
            self.ChildCountRole: b"childCount",
            self.TrackThumbnailsRole: b"trackThumbnails",
        }

    def set_items(self, items: list[dict]) -> None:
        self.beginResetModel()
        self._items = items
        self.endResetModel()
        self.countChanged.emit()

    def item_at(self, row: int) -> dict | None:
        if 0 <= row < len(self._items):
            return self._items[row]
        return None

    def item_paths(self) -> list[str]:
        return [str(item.get("path", "")) for item in self._items]

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
    playlistNavigationChanged = pyqtSignal()
    libraryNavigationChanged = pyqtSignal()
    searchResults = pyqtSignal(list)
    searchError = pyqtSignal(str)
    downloadProgress = pyqtSignal(str, float)
    downloadFinished = pyqtSignal(str, str)
    downloadError = pyqtSignal(str, str)

    def __init__(self, player: PlayerBridge, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._player = player
        self._track_title = "LIMINAL"
        self._track_artist = "Offline Media Player"
        self._is_playing = False
        self._volume = 100
        self._current_page: int = 2
        self._page_title = "Music"
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

        self._music_paths = [
            info.path
            for info in scan_directory(Path(self._music_dir), AUDIO_EXTS)
        ]
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
        self._all_music_singles: list[dict] = []
        self._all_music_albums: list[dict] = []
        self._all_video_items: list[dict] = []
        self._all_playlist_items: list[dict] = []
        self._playlist_folder_stack: list[Path] = []
        self._music_folder_stack: list[Path] = []
        self._video_folder_stack: list[Path] = []

        self._music_model = MediaListModel(self)
        self._music_singles_model = MediaListModel(self)
        self._music_albums_model = MediaListModel(self)
        self._music_section = "singles"
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

    @pyqtProperty(str, constant=True)
    def downloadDependencyError(self) -> str:
        """Allow QML to report optional download dependencies without crashing."""
        return self.downloader.availability_error(require_ffmpeg=True) or ""

    @pyqtProperty(QObject, constant=True)
    def musicModel(self) -> MediaListModel:
        return self._music_model

    @pyqtProperty(QObject, constant=True)
    def musicSinglesModel(self) -> MediaListModel:
        return self._music_singles_model

    @pyqtProperty(QObject, constant=True)
    def musicAlbumsModel(self) -> MediaListModel:
        return self._music_albums_model

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

    @pyqtProperty(bool, notify=playlistNavigationChanged)
    def playlistCanGoBack(self) -> bool:
        return bool(self._playlist_folder_stack)

    @pyqtProperty(str, notify=playlistNavigationChanged)
    def playlistBreadcrumb(self) -> str:
        return self._breadcrumb_for_stack(self._playlist_folder_stack)

    @pyqtProperty(bool, notify=libraryNavigationChanged)
    def inCollectionView(self) -> bool:
        return bool(self._folder_stack_for_page(self._current_page))

    @pyqtProperty(bool, notify=libraryNavigationChanged)
    def libraryCanGoBack(self) -> bool:
        return bool(self._folder_stack_for_page(self._current_page))

    @pyqtProperty(str, notify=libraryNavigationChanged)
    def libraryBreadcrumb(self) -> str:
        return self._breadcrumb_for_stack(self._folder_stack_for_page(self._current_page))

    @pyqtProperty(str, notify=libraryNavigationChanged)
    def collectionBannerTitle(self) -> str:
        folder = self._current_library_folder()
        return folder.name if self.inCollectionView else ""

    @pyqtProperty(str, notify=libraryNavigationChanged)
    def collectionBannerSubtitle(self) -> str:
        if not self.inCollectionView:
            return ""
        model = self._model_for_page(self._current_page)
        count = model.rowCount()
        audio = 0
        video = 0
        for row in range(count):
            item = model.item_at(row)
            if item is None or item.get("is_collection"):
                continue
            if item.get("audio_only"):
                audio += 1
            else:
                video += 1
        parts: list[str] = []
        if audio:
            parts.append(f"{audio} bài")
        if video:
            parts.append(f"{video} video")
        return " · ".join(parts) if parts else "Playlist trống"

    @pyqtProperty(str, notify=libraryNavigationChanged)
    def collectionBannerImage(self) -> str:
        if not self.inCollectionView:
            return ""
        return find_folder_preview_image(self._current_library_folder())

    @pyqtProperty(bool, notify=libraryNavigationChanged)
    def collectionHasPlayableTracks(self) -> bool:
        return bool(self._collection_media_items())

    # ── Slots ──

    @pyqtSlot(int)
    def setCurrentPage(self, page: int) -> None:
        # Playlist remains available as a storage model, but is no longer a
        # navigable top-level page.
        if page == 1:
            page = 2
        if page != 1 and self._current_page == 1:
            self._playlist_folder_stack.clear()
            self.playlistNavigationChanged.emit()
            self.libraryNavigationChanged.emit()
        if page != 2 and self._current_page == 2:
            self._music_folder_stack.clear()
            self.libraryNavigationChanged.emit()
        if page != 3 and self._current_page == 3:
            self._video_folder_stack.clear()
            self.libraryNavigationChanged.emit()
        if page in {1, 2, 3}:
            # Also refresh when the user clicks the already-selected tab.
            self._load_libraries()
        if self._current_page != page:
            self._current_page = page
            titles = {
                1: "Playlist",
                2: "Music",
                3: "Videos",
                4: "Tải xuống",
                5: "Settings",
            }
            self._page_title = titles.get(page, "Liminal")
            self.pageTitleChanged.emit()
            self.currentPageChanged.emit()
            self.libraryNavigationChanged.emit()

    @pyqtSlot(str)
    def setSearchFilter(self, text: str) -> None:
        self._filter = text.strip().lower()
        if self._current_page == 2:
            if self.inCollectionView:
                active = self._music_albums_model if self._music_section == "albums" else self._music_singles_model
                self._apply_library_filter(self._all_music_items, active)
            else:
                self._apply_library_filter(self._all_music_singles, self._music_singles_model)
                self._apply_library_filter(self._all_music_albums, self._music_albums_model)
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
        if item.get("is_collection"):
            self.openCollection(index)
            return
        if self.inCollectionView:
            self._set_playback_queue(self._collection_media_items())
        self._play_item(item)

    @pyqtSlot(int)
    def playMusicSingle(self, index: int) -> None:
        self._music_section = "singles"
        self._music_model.set_items(self._music_singles_model._items)
        self.playMedia(index)

    @pyqtSlot(int)
    def openMusicAlbum(self, index: int) -> None:
        self._music_section = "albums"
        self.openCollection(index)

    @pyqtSlot()
    def playCollection(self) -> None:
        items = self._collection_media_items()
        if not items:
            return
        self._set_playback_queue(items)
        self._play_item(items[0])

    @pyqtSlot()
    def playCollectionShuffled(self) -> None:
        items = self._collection_media_items()
        if not items:
            return
        self._set_playback_queue(items)
        if not self._shuffle_on:
            self._shuffle_on = True
            self.shuffleChanged.emit()
        self._play_item(random.choice(items))

    @pyqtSlot()
    def togglePlayCollection(self) -> None:
        if self._is_playing:
            self.togglePause()
            return
        self.playCollection()

    @pyqtSlot(int)
    def openCollection(self, index: int) -> None:
        if self._current_page not in {1, 2, 3}:
            return
        model = self._model_for_page(self._current_page)
        item = model.item_at(index)
        if item is None or not item.get("is_collection"):
            return
        self._folder_stack_for_page(self._current_page).append(Path(item["path"]))
        self._reload_library_view(self._current_page)

    @pyqtSlot()
    def goBackPlaylist(self) -> None:
        self.goBackLibrary()

    @pyqtSlot()
    def goBackLibrary(self) -> None:
        stack = self._folder_stack_for_page(self._current_page)
        if not stack:
            return
        stack.pop()
        self._reload_library_view(self._current_page)

    @pyqtSlot()
    def goBack(self) -> None:
        if self._current_page in {1, 2, 3} and self._folder_stack_for_page(self._current_page):
            self.goBackLibrary()
        elif self._current_page != 2:
            self.setCurrentPage(2)

    @pyqtSlot(str)
    def createFolder(self, name: str) -> None:
        if self._current_page not in {1, 2, 3}:
            return
        parent = self._current_library_folder()
        base = (name or "Thư mục mới").strip() or "Thư mục mới"
        candidate = parent / base
        if candidate.exists():
            n = 2
            while (parent / f"{base} ({n})").exists():
                n += 1
            candidate = parent / f"{base} ({n})"
        try:
            candidate.mkdir(parents=False, exist_ok=False)
        except OSError as exc:
            logger.error("Failed to create folder %s: %s", candidate, exc)
            return
        self._reload_library_view(self._current_page)

    @pyqtSlot(str, str)
    def moveMediaByPath(self, source_path: str, dest_folder_path: str) -> None:
        if self._current_page not in {1, 2, 3}:
            return
        src = Path(source_path)
        dest_dir = Path(dest_folder_path)
        if not src.exists() or not dest_dir.is_dir():
            return
        if src.resolve() == dest_dir.resolve() or dest_dir.resolve().is_relative_to(src.resolve()):
            return
        target = dest_dir / src.name
        if target.exists():
            return
        try:
            shutil.move(str(src), str(target))
        except OSError as exc:
            logger.error("Failed to move %s -> %s: %s", src, target, exc)
            return
        delete_metadata(str(src.resolve()))
        self._load_libraries()

    @pyqtSlot(int)
    def moveMediaOutOfFolder(self, index: int) -> None:
        if self._current_page not in {1, 2, 3}:
            return
        stack = self._folder_stack_for_page(self._current_page)
        if not stack:
            return
        model = self._model_for_page(self._current_page)
        item = model.item_at(index)
        if item is None or item.get("is_collection"):
            return
        src = Path(item["path"])
        dest_dir = stack[-1].parent
        target = dest_dir / src.name
        if target.exists():
            return
        try:
            shutil.move(str(src), str(target))
        except OSError as exc:
            logger.error("Failed to move %s out of folder: %s", src, exc)
            return
        delete_metadata(str(src.resolve()))
        self._reload_library_view(self._current_page)

    @pyqtSlot(int, int)
    def reorderCollectionItems(self, from_index: int, to_index: int) -> None:
        if self._current_page not in {1, 2, 3}:
            return
        if from_index == to_index:
            return
        model = self._model_for_page(self._current_page)
        paths = model.item_paths()
        if not (0 <= from_index < len(paths) and 0 <= to_index < len(paths)):
            return
        moved = paths.pop(from_index)
        paths.insert(to_index, moved)
        names = [Path(p).name for p in paths]
        write_order(self._current_library_folder(), names)
        self._reload_library_view(self._current_page)

    @pyqtSlot(str, str)
    def reorderCollectionByPath(self, from_path: str, to_path: str) -> None:
        if self._current_page not in {1, 2, 3}:
            return
        if not from_path or from_path == to_path:
            return
        model = self._model_for_page(self._current_page)
        paths = model.item_paths()
        try:
            from_idx = paths.index(from_path)
            to_idx = paths.index(to_path)
        except ValueError:
            return
        self.reorderCollectionItems(from_idx, to_idx)

    @pyqtSlot()
    def nextNavPage(self) -> None:
        pages = NAV_TAB_PAGES
        try:
            idx = pages.index(self._current_page)
            next_idx = (idx + 1) % len(pages)
        except ValueError:
            next_idx = 0
        self.setCurrentPage(pages[next_idx])

    @pyqtSlot()
    def previousNavPage(self) -> None:
        pages = NAV_TAB_PAGES
        try:
            idx = pages.index(self._current_page)
            prev_idx = (idx - 1) % len(pages)
        except ValueError:
            prev_idx = 0
        self.setCurrentPage(pages[prev_idx])

    @pyqtSlot()
    def quitApp(self) -> None:
        app = QApplication.instance()
        if app is not None:
            app.quit()

    @pyqtSlot(int)
    def deleteMediaAt(self, index: int) -> None:
        model = self._model_for_page(self._current_page)
        item = model.item_at(index)
        if item is None:
            return
        path = Path(item["path"])
        try:
            if path.is_dir():
                shutil.rmtree(path)
            elif path.is_file():
                path.unlink()
        except OSError as exc:
            logger.error("Failed to delete %s: %s", path, exc)
            return
        delete_metadata(str(path))
        if self._current_page == 1:
            self._reload_library_view(1)
        else:
            self._load_libraries()

    @pyqtSlot(int, str, str)
    def editMediaMetadata(self, index: int, title: str, artist: str) -> None:
        model = self._model_for_page(self._current_page)
        item = model.item_at(index)
        if item is None:
            return
        set_metadata(
            item["path"],
            title=title.strip(),
            artist=artist.strip(),
        )
        if self._current_page == 1:
            self._reload_library_view(1)
        else:
            self._load_libraries()

    @pyqtSlot(int)
    def pickMediaCover(self, index: int) -> None:
        model = self._model_for_page(self._current_page)
        item = model.item_at(index)
        if item is None:
            return
        parent = QApplication.activeWindow()
        chosen, _ = QFileDialog.getOpenFileName(
            parent,
            "Chọn ảnh bìa",
            "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)",
        )
        if not chosen:
            return
        set_cover_image(item["path"], chosen)
        if self._current_page == 1:
            self._reload_library_view(1)
        else:
            self._load_libraries()

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

    @pyqtSlot(str, str)
    def searchOnline(self, query: str, media_type: str) -> None:
        """Start an online search without blocking Qt's event loop."""
        self._search_seq += 1
        asyncio.create_task(self._search(query, media_type, self._search_seq))

    async def _search(self, query: str, media_type: str, seq: int) -> None:
        query = query.strip()
        if not query:
            if seq == self._search_seq:
                self.searchResults.emit([])
            return
        try:
            results = await asyncio.wait_for(
                self.downloader.search(query, media_type, limit=10),
                timeout=15,
            )
        except TimeoutError:
            if seq == self._search_seq:
                self.searchError.emit("Tìm kiếm quá thời gian chờ (15 giây). Vui lòng thử lại.")
            return
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
        value = url.strip()
        if not value:
            self.downloadError.emit("", "URL hoặc video ID không hợp lệ.")
            return
        media_type = "music" if kind in {"audio", "music"} else kind
        asyncio.create_task(self._download(value, media_type))

    async def _download(self, url: str, media_type: str) -> None:
        active_id = url

        def hook(data: dict) -> None:
            nonlocal active_id
            info = data.get("info_dict") or {}
            active_id = str(info.get("id") or active_id)
            if data.get("status") != "downloading":
                return
            downloaded = float(data.get("downloaded_bytes") or 0)
            total = float(data.get("total_bytes") or data.get("total_bytes_estimate") or 0)
            # yt-dlp provides real byte counts; estimates are used only when the
            # server does not announce a Content-Length.
            percent = min(100.0, downloaded / total * 100.0) if total else 0.0
            self.downloadProgress.emit(active_id, percent)

        if media_type not in {"music", "video"}:
            self.downloadError.emit(active_id, "Loại media không được hỗ trợ.")
            return
        try:
            video_id, file_path = await self.downloader.download(url, media_type, hook)
        except DownloadFailed as exc:
            logger.exception("Media download failed for %r", url)
            self.downloadError.emit(active_id, str(exc))
            return

        self.downloadFinished.emit(video_id, file_path)
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

    @pyqtSlot()
    def seekBackward10(self) -> None:
        self._player.seek(-10)

    @pyqtSlot()
    def seekForward10(self) -> None:
        self._player.seek(10)

    @pyqtSlot(float)
    def setVolume(self, vol: float) -> None:
        vol = max(0, min(100, int(round(vol))))
        if vol > 0 and self._muted:
            self._muted = False
            self.mutedChanged.emit()
        if self._volume != vol:
            self._volume = vol
            self.volumeChanged.emit()
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
            2: self._music_albums_model if self._music_section == "albums" else self._music_singles_model,
            3: self.videoModel,
        }.get(page, self.playlistModel)

    def _target_dir(self, target: str) -> Path:
        if target == "music":
            return Path(self._music_dir)
        if target == "video":
            return Path(self._video_dir)
        return Path(self._playlist_dir)

    def _folder_stack_for_page(self, page: int) -> list[Path]:
        return {
            1: self._playlist_folder_stack,
            2: self._music_folder_stack,
            3: self._video_folder_stack,
        }.get(page, self._playlist_folder_stack)

    def _root_dir_for_page(self, page: int) -> Path:
        return {
            1: Path(self._playlist_dir),
            2: Path(self._music_dir),
            3: Path(self._video_dir),
        }.get(page, Path(self._playlist_dir))

    def _breadcrumb_for_stack(self, stack: list[Path]) -> str:
        if not stack:
            return ""
        return " / ".join(p.name for p in stack)

    def _current_library_folder(self) -> Path:
        stack = self._folder_stack_for_page(self._current_page)
        if stack:
            return stack[-1]
        return self._root_dir_for_page(self._current_page)

    def _current_playlist_folder(self) -> Path:
        return self._current_library_folder() if self._current_page == 1 else Path(self._playlist_dir)

    def _playlist_infos_to_items(self, infos: list[MediaInfo]) -> list[dict]:
        items: list[dict] = []
        for i, info in enumerate(infos):
            if info.kind == MediaKind.FILE:
                audio_only = Path(info.path).suffix.lower() in AUDIO_EXTS
            elif info.kind in (MediaKind.ALBUM, MediaKind.FOLDER):
                audio_only = True
            else:
                audio_only = False
            items.append(_media_item(info, i, audio_only=audio_only))
        return items

    def _reload_library_view(self, page: int) -> None:
        folder = self._folder_stack_for_page(page)[-1] if self._folder_stack_for_page(page) else self._root_dir_for_page(page)
        infos = scan_library_folder(folder)
        items = self._playlist_infos_to_items(infos)
        if page == 1:
            self._all_playlist_items = items
            self._apply_library_filter(self._all_playlist_items, self.playlistModel)
            self.playlistNavigationChanged.emit()
        elif page == 2:
            self._all_music_items = items
            if self._folder_stack_for_page(page):
                active = self._music_albums_model if self._music_section == "albums" else self._music_singles_model
                self._apply_library_filter(self._all_music_items, active)
                self._music_model.set_items(active._items)
            else:
                self._all_music_singles = [item for item in items if not item.get("is_collection")]
                self._all_music_albums = [item for item in items if item.get("is_collection")]
                self._apply_library_filter(self._all_music_singles, self._music_singles_model)
                self._apply_library_filter(self._all_music_albums, self._music_albums_model)
                self._music_model.set_items(self._music_singles_model._items)
        elif page == 3:
            self._all_video_items = items
            self._apply_library_filter(self._all_video_items, self.videoModel)
        self.libraryNavigationChanged.emit()

    def _reload_playlist_view(self) -> None:
        self._reload_library_view(1)

    def _load_libraries(self) -> None:
        self._music_paths = [
            info.path
            for info in scan_directory(Path(self._music_dir), AUDIO_EXTS)
        ]
        self._reload_library_view(1)
        self._reload_library_view(2)
        self._reload_library_view(3)

        preview_limit = 12
        flat_music = self._playlist_infos_to_items(
            scan_directory(Path(self._music_dir), AUDIO_EXTS)
        )
        flat_video = self._playlist_infos_to_items(
            scan_directory(Path(self._video_dir), VIDEO_EXTS)
        )
        self._media_music_preview = flat_music[:preview_limit]
        self._media_video_preview = flat_video[:preview_limit]
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

    def _collection_media_items(self) -> list[dict]:
        if not self.inCollectionView:
            return []
        model = self._model_for_page(self._current_page)
        items: list[dict] = []
        for row in range(model.rowCount()):
            item = model.item_at(row)
            if item is None or item.get("is_collection"):
                continue
            path = item.get("path") or item.get("url") or ""
            if not path:
                continue
            if not item.get("audio_only") and not _is_remote(path):
                if not Path(path).exists():
                    continue
            items.append(item)
        return items

    def _set_playback_queue(self, items: list[dict]) -> None:
        self._music_paths = [
            path
            for item in items
            if item.get("audio_only")
            and (path := (item.get("path") or item.get("url") or ""))
        ]

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
