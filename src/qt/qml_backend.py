"""QML ↔ Python bridge for Liminal."""

from __future__ import annotations

import logging
import random
import asyncio
import shutil
import srt
from dataclasses import dataclass, replace
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
    QSettings,
)
from PyQt6.QtGui import QDesktopServices, QGuiApplication, QWindow
from PyQt6.QtWidgets import QApplication, QFileDialog

from src.config import AUDIO_EXTS, VIDEO_EXTS, mpv_audio_gain_factor
from src.downloader import (
    Downloader,
    Download403Failed,
    DownloadFailed,
    _normalize_video_quality,
    extract_youtube_id,
)
from src.folder_order import write_order
from src.media_links import (
    add_track_to_album,
    playlist_contains_media,
    canonical_path,
    delete_track_completely,
    remove_track_from_album,
    video_can_move_to_series,
    audio_can_move_to_playlist,
)
from src.metadata_store import (
    delete_metadata,
    get_watched_progress,
    migrate_metadata,
    get_metadata,
    read_embedded_metadata,
    find_video_subtitle_paths,
    read_video_thumbnail,
    resolve_display,
    resolve_source_id,
    resolve_source_url,
    canonical_source_url,
    set_cover_image,
    set_metadata,
    set_watched_progress,
)
from src.models import MediaInfo, MediaKind, PlaybackStatus
from src.player import PlayerBridge
from src.scanner import (
    find_folder_preview_image,
    find_folder_track_thumbnails,
    scan_directory,
    scan_library_folder,
    scan_music_library_bundle,
    scan_video_library_bundle,
    resolved_paths_in_child_folders,
)
from src.thumbnail_queue import get_thumbnail_queue
from src.playlist_layout import (
    collect_playlist_tracks,
    playlist_download_subdir,
    track_share_payload,
)
from src.series_layout import (
    apply_tap_assignments,
    apply_tap_order,
    collect_series_videos,
    detect_series_rows,
    episode_download_subdir,
    episode_share_payload,
    format_episode_subtitle,
    save_series_rows,
)
from src.settings_store import load_raw_settings, load_settings, read_settings_document_or_none, save_raw_settings, save_settings
from src.state_store import load_raw_state, save_raw_state
from src.ui_config import load_ui_config, open_config_dir

logger = logging.getLogger(__name__)

_PLAYER_BAR_IDLE_MS = 10 * 60 * 1000
_LIBRARY_HOTLOAD_MS = 10 * 1000
_LIBRARY_HOTLOAD_DOWNLOAD_MS = 10 * 1000
_SHARED_PROGRESS_DEBOUNCE_MS = 1000

APP_ICON_PATH = Path(__file__).resolve().parent / "liminal.png"

ACCENT_COLORS = [
    "#4facfe",
    "#a855f7",
    "#38e6ff",
    "#7850ff",
    "#6366f1",
]

ALL_MUSICS_VIRTUAL_PATH = "__liminal__:all-musics"
ALL_MUSICS_TITLE = "All Musics"


def _is_remote(path: str) -> bool:
    return path.startswith(("http://", "https://"))


def _track_path_available(path: str) -> bool:
    value = (path or "").strip()
    if not value:
        return False
    if _is_remote(value):
        return True
    try:
        return Path(value).exists()
    except OSError:
        return False


def _metadata_path(item: dict) -> str:
    return item.get("canonical_path") or item.get("path") or ""


def _resolve_metadata_path(path: str) -> str:
    """Map a UI path (e.g. playlist symlink) to the metadata storage key."""
    value = path.strip()
    if not value:
        return ""
    try:
        resolved = Path(value)
        if resolved.is_file() or resolved.is_symlink():
            return str(canonical_path(resolved))
        if resolved.is_dir():
            return str(resolved.resolve())
    except OSError:
        pass
    return value


def _normalize_artist(value: str) -> str:
    artist = str(value or "").strip()
    if artist.lower() in {"", "unknown artist", "video", "unknown", "music"}:
        return ""
    return artist


def _compute_watched_percent(path: str) -> float:
    """Return 0-100 watched percentage for a video file path."""
    if not path:
        return 0.0
    pos, dur = get_watched_progress(path)
    if dur <= 0:
        return 0.0
    return max(0.0, min(100.0, pos / dur * 100.0))


@dataclass(frozen=True)
class _FolderStackEntry:
    path: Path
    inode: tuple[int, int] | None = None


def _folder_inode(path: Path) -> tuple[int, int] | None:
    try:
        resolved = path.resolve()
        if not resolved.exists():
            return None
        stat = resolved.stat()
        return (stat.st_dev, stat.st_ino)
    except OSError:
        return None


def _media_item(info: MediaInfo, index: int, *, audio_only: bool = True) -> dict:
    is_collection = info.kind in (MediaKind.ALBUM, MediaKind.VIDEO_PLAYLIST, MediaKind.FOLDER)
    if is_collection:
        audio_only = info.kind in (MediaKind.ALBUM, MediaKind.FOLDER)
    canonical = info.canonical_path or info.path
    return {
        "title": info.title,
        "subtitle": info.subtitle or info.artist or ("Music" if audio_only else "Video"),
        "artist": _normalize_artist(info.artist),
        "path": info.path,
        "canonical_path": canonical,
        "url": info.url or info.path,
        "track_id": info.track_id or canonical or info.url or info.path,
        "duration": info.duration,
        "image": info.image or (info.preview_images[0] if is_collection and info.preview_images else ""),
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
        "watched_percent": 0.0 if audio_only else _compute_watched_percent(canonical),
    }


class MediaListModel(QAbstractListModel):
    """List model for GridView media cards."""

    countChanged = pyqtSignal()

    TitleRole = Qt.ItemDataRole.UserRole + 1
    SubtitleRole = Qt.ItemDataRole.UserRole + 2
    ArtistRole = Qt.ItemDataRole.UserRole + 3
    ImageSourceRole = Qt.ItemDataRole.UserRole + 4
    AccentColorRole = Qt.ItemDataRole.UserRole + 5
    PathRole = Qt.ItemDataRole.UserRole + 6
    AudioOnlyRole = Qt.ItemDataRole.UserRole + 7
    UrlRole = Qt.ItemDataRole.UserRole + 8
    DurationRole = Qt.ItemDataRole.UserRole + 9
    TrackIdRole = Qt.ItemDataRole.UserRole + 10
    IsRemoteRole = Qt.ItemDataRole.UserRole + 11
    DownloadPercentRole = Qt.ItemDataRole.UserRole + 12
    DownloadStatusRole = Qt.ItemDataRole.UserRole + 13
    IsDownloadingRole = Qt.ItemDataRole.UserRole + 14
    IsCollectionRole = Qt.ItemDataRole.UserRole + 15
    KindRole = Qt.ItemDataRole.UserRole + 16
    ChildCountRole = Qt.ItemDataRole.UserRole + 17
    TrackThumbnailsRole = Qt.ItemDataRole.UserRole + 18
    SeasonRole = Qt.ItemDataRole.UserRole + 19
    EpisodeRole = Qt.ItemDataRole.UserRole + 20
    WatchedPercentRole = Qt.ItemDataRole.UserRole + 21

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
            self.ArtistRole: "artist",
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
            self.SeasonRole: "season",
            self.EpisodeRole: "episode",
            self.WatchedPercentRole: "watched_percent",
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
        if role in (self.SeasonRole, self.EpisodeRole):
            return int(value or 0)
        if role == self.TrackThumbnailsRole:
            return list(value or [])
        if role == self.DownloadPercentRole:
            return float(value or 0.0)
        if role == self.WatchedPercentRole:
            return float(value or 0.0)
        return value

    def roleNames(self) -> dict[int, bytes]:
        return {
            self.TitleRole: b"title",
            self.SubtitleRole: b"subtitle",
            self.ArtistRole: b"artist",
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
            self.SeasonRole: b"season",
            self.EpisodeRole: b"episode",
            self.WatchedPercentRole: b"watchedPercent",
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

    def update_image_by_path(
        self,
        path: str,
        image: str,
        *,
        preview_images: list[str] | None = None,
    ) -> bool:
        """Update card artwork for *path* without resetting the whole model."""
        if not image:
            return False
        try:
            resolved = str(Path(path).resolve())
        except OSError:
            resolved = path
        candidates = {path, resolved}
        changed = False
        for row, item in enumerate(self._items):
            item_path = str(item.get("canonical_path") or item.get("path") or "")
            try:
                item_resolved = str(Path(item_path).resolve()) if item_path else ""
            except OSError:
                item_resolved = item_path
            if item_path not in candidates and item_resolved not in candidates:
                continue
            if item.get("image") == image and (
                preview_images is None or item.get("preview_images") == preview_images
            ):
                return False
            item["image"] = image
            if preview_images is not None:
                item["preview_images"] = list(preview_images)
            idx = self.index(row, 0)
            roles = [self.ImageSourceRole]
            if preview_images is not None:
                roles.append(self.TrackThumbnailsRole)
            self.dataChanged.emit(idx, idx, roles)
            changed = True
            break
        return changed


@dataclass(frozen=True)
class _DownloadJob:
    url: str
    media_type: str
    output_subdir: str
    quality: str = "1080"
    retry_403: bool = False


_LARGE_BATCH_THRESHOLD = 30
_GOOD_NETWORK_BPS = 512 * 1024  # 512 KB/s
_MAX_CONCURRENT_DOWNLOADS = 2


class AppBackend(QObject):
    """Exposed to QML as ``backend`` context property."""

    trackTitleChanged = pyqtSignal()
    trackArtistChanged = pyqtSignal()
    trackThumbnailChanged = pyqtSignal()
    isPlayingChanged = pyqtSignal()
    volumeChanged = pyqtSignal()
    videoPlaybackModeChanged = pyqtSignal()
    currentPageChanged = pyqtSignal()
    positionChanged = pyqtSignal()
    durationChanged = pyqtSignal()
    shuffleChanged = pyqtSignal()
    loopModeChanged = pyqtSignal()
    mutedChanged = pyqtSignal()
    hasMediaChanged = pyqtSignal()
    playerBarVisibleChanged = pyqtSignal()
    mediaRootChanged = pyqtSignal()
    musicDirChanged = pyqtSignal()
    videoDirChanged = pyqtSignal()
    settingsSavedChanged = pyqtSignal()
    pageTitleChanged = pyqtSignal()
    downloadQualityChanged = pyqtSignal()
    downloadConcurrencyChanged = pyqtSignal()
    ytDlpUpdateStatusChanged = pyqtSignal()
    libraryNavigationChanged = pyqtSignal()
    primaryPlayLabelChanged = pyqtSignal()
    musicSearchChanged = pyqtSignal()
    videoSearchChanged = pyqtSignal()
    searchQueryChanged = pyqtSignal()
    playlistOrderUndoChanged = pyqtSignal()
    searchResults = pyqtSignal(list)
    searchError = pyqtSignal(str)
    playlistLinkReady = pyqtSignal(str, list)
    playlistQueued = pyqtSignal(str, str, list)
    linkQueueError = pyqtSignal(str, str)
    downloadProgress = pyqtSignal(str, float)
    downloadFinished = pyqtSignal(str, str)
    downloadError = pyqtSignal(str, str)
    downloadJobStarted = pyqtSignal(str)
    downloadJobRequeued = pyqtSignal(str)
    seriesAiSortLoadingChanged = pyqtSignal()
    seriesAiSortFinished = pyqtSignal(list)
    seriesAiSortError = pyqtSignal(str)
    focusModeChanged = pyqtSignal()
    fullScreenChanged = pyqtSignal()
    videoStateChanged = pyqtSignal()
    focusModeStartPositionMsChanged = pyqtSignal()

    def __init__(
        self,
        player: PlayerBridge,
        *,
        ui_config: dict | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._player = player
        self._ui_config = ui_config or load_ui_config()
        self._track_title = "LIMINAL"
        self._track_artist = "Offline Media Player"
        self._track_thumbnail = ""
        self._playback_items: dict[str, dict] = {}
        self._is_playing = False
        self._current_page: int = 2
        self._page_title = "Music"
        self._filter = ""
        self._app_icon_url = QUrl.fromLocalFile(str(APP_ICON_PATH.resolve())).toString()
        self._main_window: QWindow | None = None
        self._settings = QSettings("Liminal", "MediaApp")
        self._engine = None

        settings = load_settings()
        self._media_root = settings["media_root"]
        self._music_dir = settings["music_dir"]
        self._video_dir = settings["video_dir"]
        self._search_seq = 0
        self._settings_saved = True
        self._download_queue: asyncio.Queue[_DownloadJob] | None = None
        self._download_worker_started = False
        self._deferred_403_jobs: list[_DownloadJob] = []
        self._download_jobs_in_progress = 0
        self._pending_video_downloads = 0
        self._download_speed_ema = 0.0
        self._published_download_concurrency = 1
        self.downloader = Downloader(
            Path(self._music_dir),
            Path(self._video_dir),
        )

        raw = load_raw_settings()
        state = load_raw_state()
        self._download_quality: str = _normalize_video_quality(
            str(raw.get("download_quality", "1080"))
        )
        self._volume = max(0, min(100, int(raw.get("volume", 100))))
        self._muted = bool(raw.get("muted", False))
        playback_mode = str(raw.get("video_playback_backend", "inapp")).strip().lower()
        self._video_playback_mode = playback_mode if playback_mode in {"inapp", "mpv"} else "inapp"
        self._player_bar_always_visible = bool(
            self._ui_config.get("player_bar", {}).get("always_visible", False)
        )
        self._yt_dlp_update_status: str = ""
        self._volume_save_timer = QTimer(self)
        self._volume_save_timer.setSingleShot(True)
        self._volume_save_timer.setInterval(400)
        self._volume_save_timer.timeout.connect(self._persist_volume_prefs)

        self._library_hotload_timer = QTimer(self)
        self._library_hotload_timer.setInterval(_LIBRARY_HOTLOAD_MS)
        self._library_hotload_timer.timeout.connect(self._on_library_hotload_tick)

        self._shared_progress_save_timer = QTimer(self)
        self._shared_progress_save_timer.setSingleShot(True)
        self._shared_progress_save_timer.setInterval(_SHARED_PROGRESS_DEBOUNCE_MS)
        self._shared_progress_save_timer.timeout.connect(self._flush_shared_progress_state)
        self._shared_series_pending_persist: set[str] = set()
        self._shared_playlist_pending_persist: set[str] = set()

        self._video_progress_timer = QTimer(self)
        self._video_progress_timer.setInterval(5000)
        self._video_progress_timer.timeout.connect(self._save_video_progress)
        self._active_video_download_subdirs: dict[str, int] = {}
        self._active_music_download_subdirs: dict[str, int] = {}

        self._music_paths: list[str] = []
        self._current_path = ""
        self._current_audio_only = True
        self._shuffle_on = False
        self._loop_mode = 0  # 0=off, 1=repeat all, 2=repeat one
        self._position = 0.0
        self._duration = 0.0
        self._has_media = False

        # ── Session restore ────────────────────────────────────────────────────────────
        # has_played_before: False on fresh install, True after first ever play.
        # When True, the PlayerBar is always shown (never hidden by idle timer).
        self._has_played_before: bool = bool(state.get("has_played_before", False))
        last_title = str(state.get("last_track_title", ""))
        last_artist = str(state.get("last_track_artist", ""))
        last_thumbnail = str(state.get("last_track_thumbnail", ""))
        last_path = str(state.get("last_track_path", ""))
        last_audio_only = bool(state.get("last_track_audio_only", True))
        self._last_track_position = float(state.get("last_track_position", 0.0))

        if (
            self._has_played_before
            and last_title
            and last_path
            and _track_path_available(last_path)
        ):
            self._track_title = last_title
            self._track_artist = last_artist
            self._track_thumbnail = last_thumbnail
            self._set_current_path(last_path)
            self._current_audio_only = last_audio_only
            self._has_media = True
            # Also set the initial position slider to the last saved position
            self._position = self._last_track_position

        # Show bar only when a restorable track exists (or always-visible setting).
        self._player_bar_visible = self._player_bar_always_visible or bool(
            self._current_path and _track_path_available(self._current_path)
        )
        # ── End session restore ─────────────────────────────────────────────────────────

        self._player_bar_idle_timer = QTimer(self)
        self._player_bar_idle_timer.setSingleShot(True)
        self._player_bar_idle_timer.setInterval(_PLAYER_BAR_IDLE_MS)
        self._player_bar_idle_timer.timeout.connect(self._on_player_bar_idle_timeout)
        self._media_music_preview: list[dict] = []
        self._media_video_preview: list[dict] = []

        self._all_music_items: list[dict] = []
        self._all_music_singles: list[dict] = []
        self._all_music_albums: list[dict] = []
        self._all_music_tracks: list[dict] = []
        self._all_video_items: list[dict] = []
        self._all_video_series: list[dict] = []
        self._all_video_movies: list[dict] = []
        self._all_video_my_movies: list[dict] = []
        self._all_video_shared: list[dict] = []
        self._all_music_shared: list[dict] = []
        self._all_video_tracks: list[dict] = []
        self._music_track_infos: list[MediaInfo] | None = None
        self._video_track_infos: list[MediaInfo] | None = None
        self._music_root_infos: list[MediaInfo] | None = None
        self._video_root_infos: list[MediaInfo] | None = None
        self._music_library_loaded = False
        self._video_library_loaded = False
        self._music_scan_running = False
        self._video_scan_running = False
        self._music_source_ids_ready = False
        self._video_source_ids_ready = False
        self._music_folder_stack: list[_FolderStackEntry] = []
        self._video_folder_stack: list[_FolderStackEntry] = []
        self._shared_series_index = -1
        self._shared_playlist_index = -1
        self._movie_detail_index = -1
        self._shared_movie_detail_index = -1
        self._in_focus_mode = False
        self._focus_mode_title = ""
        self._focus_mode_source = ""
        self._focus_mode_start_position_ms = 0
        self._is_full_screen = False
        self._video_is_playing = False
        self._video_position = 0
        self._video_duration = 0
        self._subtitle_cues: list[dict] = []
        self._subtitle_available = False
        self._subtitle_index = 0
        self._current_episode_list: list[dict] = []
        self._current_episode_index = -1
        self._current_episode_series_key = ""
        self._series_ai_loading = False
        self._playlist_order_undo: dict[str, list[str]] = {}
        self._music_source_ids: set[str] = set()
        self._video_source_ids: set[str] = set()

        self._music_model = MediaListModel(self)
        self._music_singles_model = MediaListModel(self)
        self._music_albums_model = MediaListModel(self)
        self._music_search_model = MediaListModel(self)
        self._music_shared_model = MediaListModel(self)
        self._music_section = "singles"
        self._video_model = MediaListModel(self)
        self._video_series_model = MediaListModel(self)
        self._video_movies_model = MediaListModel(self)
        self._video_my_movies_model = MediaListModel(self)
        self._video_shared_model = MediaListModel(self)
        self._video_search_model = MediaListModel(self)
        self._video_section = "movies"
        self._media_music_model = MediaListModel(self)
        self._media_video_model = MediaListModel(self)

        self._player.state_changed.connect(self._on_state_changed)
        self._player.position_changed.connect(self._on_position_changed)
        self._player.track_ended.connect(self._on_track_ended)

        self.downloadProgress.connect(self._on_shared_download_progress)
        self.downloadFinished.connect(self._on_shared_download_finished)
        self.downloadError.connect(self._on_shared_download_error)
        self.downloadJobStarted.connect(self._on_shared_download_started)

        self.isPlayingChanged.connect(self.primaryPlayLabelChanged.emit)
        self.trackTitleChanged.connect(self.primaryPlayLabelChanged.emit)
        self.libraryNavigationChanged.connect(self.primaryPlayLabelChanged.emit)

        queue = get_thumbnail_queue()
        queue.setParent(self)
        queue.thumbnailReady.connect(self._on_thumbnail_queue_ready)

    def load_initial_page(self) -> None:
        """Load the startup tab's library once QML is ready."""
        if self._current_page == 2:
            self._ensure_music_library_loaded()
            if self._music_library_loaded:
                self._sync_library_page_view(2)
        elif self._current_page == 3:
            self._ensure_video_library_loaded()
            if self._video_library_loaded:
                self._sync_library_page_view(3)

    def _refresh_visible_library_views(self) -> None:
        """Re-push library models after the window becomes visible."""
        if self._music_library_loaded and self._current_page == 2:
            self._sync_library_page_view(2)
        if self._video_library_loaded and self._current_page == 3:
            self._sync_library_page_view(3)

    def preload_libraries(self) -> None:
        """Warm music/video indexes at startup so the first tab opens faster."""
        if not self._music_library_loaded and not self._music_scan_running:
            self._start_music_library_scan(refresh=False)
        if not self._video_library_loaded and not self._video_scan_running:
            self._start_video_library_scan(refresh=False)

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
    def musicSearchModel(self) -> MediaListModel:
        return self._music_search_model

    @pyqtProperty(QObject, constant=True)
    def musicSharedModel(self) -> MediaListModel:
        return self._music_shared_model

    @pyqtProperty(bool, notify=musicSearchChanged)
    def musicSearchActive(self) -> bool:
        return bool(self._filter) and self._current_page == 2 and not self.inCollectionView

    @pyqtProperty(QObject, constant=True)
    def videoModel(self) -> MediaListModel:
        return self._video_model

    @pyqtProperty(QObject, constant=True)
    def videoSeriesModel(self) -> MediaListModel:
        return self._video_series_model

    @pyqtProperty(QObject, constant=True)
    def videoMoviesModel(self) -> MediaListModel:
        return self._video_movies_model

    @pyqtProperty(QObject, constant=True)
    def videoMyMoviesModel(self) -> MediaListModel:
        return self._video_my_movies_model

    @pyqtProperty(QObject, constant=True)
    def videoSharedModel(self) -> MediaListModel:
        return self._video_shared_model

    @pyqtProperty(QObject, constant=True)
    def videoSearchModel(self) -> MediaListModel:
        return self._video_search_model

    @pyqtProperty(bool, notify=libraryNavigationChanged)
    def videoSearchActive(self) -> bool:
        return bool(self._filter) and self._current_page == 3 and not self.inCollectionView

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

    @pyqtProperty(str, notify=trackThumbnailChanged)
    def trackThumbnail(self) -> str:
        return self._track_thumbnail

    @pyqtProperty(bool, notify=isPlayingChanged)
    def isPlaying(self) -> bool:
        return self._is_playing

    @pyqtProperty(int, notify=volumeChanged)
    def volume(self) -> int:
        return self._volume

    @pyqtProperty(str, notify=videoPlaybackModeChanged)
    def videoPlaybackMode(self) -> str:
        return self._video_playback_mode

    @pyqtProperty(float, constant=True)
    def audioGainFactor(self) -> float:
        return mpv_audio_gain_factor()

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

    @pyqtProperty(int, notify=loopModeChanged)
    def loopMode(self) -> int:
        return self._loop_mode

    @pyqtProperty(bool, notify=mutedChanged)
    def muted(self) -> bool:
        return self._muted

    @pyqtProperty(bool, notify=hasMediaChanged)
    def hasMedia(self) -> bool:
        return self._has_media

    @pyqtProperty(bool, notify=playerBarVisibleChanged)
    def playerBarVisible(self) -> bool:
        return self._player_bar_visible

    @pyqtProperty(str, notify=mediaRootChanged)
    def mediaRoot(self) -> str:
        return self._media_root

    @pyqtProperty(float, notify=mediaRootChanged)
    def freeDiskSpaceGB(self) -> float:
        import shutil
        try:
            path = self._media_root
            if not path:
                return 0.0
            p = Path(path).expanduser().resolve()
            while not p.exists() and p.parent != p:
                p = p.parent
            usage = shutil.disk_usage(str(p))
            return usage.free / (1024 ** 3)
        except Exception:
            return 0.0


    @pyqtProperty(str, notify=musicDirChanged)
    def musicDir(self) -> str:
        return self._music_dir

    @pyqtProperty(str, notify=videoDirChanged)
    def videoDir(self) -> str:
        return self._video_dir

    @pyqtProperty(bool, notify=settingsSavedChanged)
    def settingsSaved(self) -> bool:
        return self._settings_saved

    @pyqtProperty(str, notify=downloadQualityChanged)
    def downloadQuality(self) -> str:
        return self._download_quality

    @pyqtProperty(int, notify=downloadConcurrencyChanged)
    def downloadConcurrency(self) -> int:
        return self._published_download_concurrency

    @pyqtProperty(str, notify=ytDlpUpdateStatusChanged)
    def ytDlpUpdateStatus(self) -> str:
        return self._yt_dlp_update_status

    @pyqtProperty(bool, notify=libraryNavigationChanged)
    def inSharedSeriesView(self) -> bool:
        return self._shared_series_index >= 0

    @pyqtProperty(bool, notify=libraryNavigationChanged)
    def inSharedPlaylistView(self) -> bool:
        return self._shared_playlist_index >= 0

    @pyqtProperty(bool, notify=libraryNavigationChanged)
    def inMusicDetailView(self) -> bool:
        return (self._current_page == 2 and self.inCollectionView) or self.inSharedPlaylistView

    @pyqtProperty(bool, notify=libraryNavigationChanged)
    def inMovieDetailView(self) -> bool:
        return self._movie_detail_index >= 0 or self._shared_movie_detail_index >= 0

    @pyqtProperty(bool, notify=libraryNavigationChanged)
    def inVideoDetailView(self) -> bool:
        return self.inCollectionView or self.inSharedSeriesView or self.inMovieDetailView

    @pyqtProperty(bool, notify=libraryNavigationChanged)
    def movieDetailIsShared(self) -> bool:
        return self._shared_movie_detail_index >= 0

    @pyqtProperty(bool, notify=focusModeChanged)
    def inFocusMode(self) -> bool:
        return self._in_focus_mode

    @pyqtProperty(str, notify=focusModeChanged)
    def focusModeTitle(self) -> str:
        return self._focus_mode_title

    @pyqtProperty(str, notify=focusModeChanged)
    def focusModeSource(self) -> str:
        return self._focus_mode_source

    @pyqtProperty(int, notify=focusModeStartPositionMsChanged)
    def focusModeStartPositionMs(self) -> int:
        return self._focus_mode_start_position_ms

    @focusModeStartPositionMs.setter
    def focusModeStartPositionMs(self, value: int) -> None:
        if self._focus_mode_start_position_ms != value:
            self._focus_mode_start_position_ms = value
            self.focusModeStartPositionMsChanged.emit()

    @pyqtProperty(bool, notify=fullScreenChanged)
    def isFullScreen(self) -> bool:
        return self._is_full_screen

    @pyqtProperty(bool, notify=videoStateChanged)
    def videoIsPlaying(self) -> bool:
        return self._video_is_playing

    @pyqtProperty(int, notify=videoStateChanged)
    def videoPosition(self) -> int:
        return self._video_position

    @pyqtProperty(bool, notify=videoStateChanged)
    def subtitleAvailable(self) -> bool:
        return self._subtitle_available

    @pyqtProperty(str, notify=videoStateChanged)
    def currentSubtitleText(self) -> str:
        if not self._subtitle_available or not self._subtitle_cues:
            return ""

        position = max(0, self._video_position)
        index = min(max(0, self._subtitle_index), len(self._subtitle_cues) - 1)

        # Most position updates move forward by a few milliseconds. Seeking
        # backwards is handled by walking from the last known cue instead of
        # scanning the whole subtitle list on every videoStateChanged signal.
        if position < self._subtitle_cues[index]["start_ms"]:
            while index > 0 and position < self._subtitle_cues[index]["start_ms"]:
                index -= 1
        else:
            while (
                index + 1 < len(self._subtitle_cues)
                and position >= self._subtitle_cues[index]["end_ms"]
            ):
                index += 1

        self._subtitle_index = index
        cue = self._subtitle_cues[index]
        if cue["start_ms"] <= position < cue["end_ms"]:
            return cue["text"]
        return ""

    @pyqtProperty(int, notify=videoStateChanged)
    def videoDuration(self) -> int:
        return self._video_duration

    @pyqtProperty(bool, notify=videoStateChanged)
    def hasNextEpisode(self) -> bool:
        return (
            self._current_episode_index >= 0
            and self._current_episode_index < len(self._current_episode_list) - 1
        )

    @pyqtProperty(bool, notify=videoStateChanged)
    def hasPreviousEpisode(self) -> bool:
        return self._current_episode_index > 0

    @pyqtProperty(str, notify=videoStateChanged)
    def currentEpisodeLabel(self) -> str:
        if self._current_episode_index < 0 or self._current_episode_index >= len(self._current_episode_list):
            return ""
        episode = self._current_episode_list[self._current_episode_index]
        season = int(episode.get("season") or 1)
        number = int(episode.get("episode") or 1)
        return f"S{season:02d}E{number:02d}"

    @pyqtProperty(list, notify=videoStateChanged)
    def currentEpisodeList(self) -> list[dict]:
        return self._current_episode_list

    @pyqtProperty(int, notify=videoStateChanged)
    def currentEpisodeIndex(self) -> int:
        return self._current_episode_index

    @pyqtProperty(bool, notify=libraryNavigationChanged)
    def inCollectionView(self) -> bool:
        return bool(self._folder_stack_for_page(self._current_page))

    @pyqtProperty(bool, notify=libraryNavigationChanged)
    def libraryCanGoBack(self) -> bool:
        if self.inMovieDetailView or self.inSharedPlaylistView:
            return True
        return bool(self._folder_stack_for_page(self._current_page))

    @pyqtProperty(str, notify=libraryNavigationChanged)
    def libraryBreadcrumb(self) -> str:
        return self._breadcrumb_for_stack(self._folder_stack_for_page(self._current_page))

    def _current_movie_detail_item(self) -> dict | None:
        if self._movie_detail_index >= 0:
            return self._video_my_movies_model.item_at(self._movie_detail_index)
        if self._shared_movie_detail_index >= 0:
            return self._video_shared_model.item_at(self._shared_movie_detail_index)
        return None

    @pyqtProperty(str, notify=libraryNavigationChanged)
    def collectionBannerTitle(self) -> str:
        if self.inMovieDetailView:
            item = self._current_movie_detail_item()
            return str(item.get("title") or "") if item else ""
        if self.inSharedSeriesView:
            item = self._video_shared_model.item_at(self._shared_series_index)
            return str(item.get("title") or "") if item else ""
        if self.inSharedPlaylistView:
            item = self._music_shared_model.item_at(self._shared_playlist_index)
            return str(item.get("title") or "") if item else ""
        if not self.inCollectionView:
            return ""
        stack = self._folder_stack_for_page(self._current_page)
        if stack and self._is_all_musics_virtual(stack[-1].path):
            return ALL_MUSICS_TITLE
        folder = self._current_library_folder()
        try:
            folder_key = str(folder.resolve())
        except OSError:
            folder_key = str(folder)
        display = resolve_display(
            folder_key,
            default_title=folder.name,
            default_image=find_folder_preview_image(folder) if folder.exists() else "",
        )
        return display["title"]

    @pyqtProperty(str, notify=libraryNavigationChanged)
    def collectionBannerSubtitle(self) -> str:
        if self.inMovieDetailView:
            item = self._current_movie_detail_item()
            if item is None:
                return ""
            parts: list[str] = []
            duration = str(item.get("duration") or "").strip()
            if duration and duration != "--:--":
                parts.append(duration)
            if self.movieDetailIsShared:
                if item.get("download_status") == "done" or self._shared_item_in_library(item):
                    parts.append("Đã tải")
                elif item.get("is_downloading"):
                    parts.append(f"Đang tải {int(item.get('download_percent') or 0)}%")
                else:
                    parts.append("Chưa tải")
            return " · ".join(parts) if parts else ""
        if self.inSharedSeriesView:
            item = self._video_shared_model.item_at(self._shared_series_index)
            if item is None:
                return ""
            episodes = list(item.get("episodes") or [])
            downloaded = sum(1 for ep in episodes if self._episode_in_library(ep))
            total = len(episodes)
            if total:
                return f"{downloaded}/{total} tập đã tải"
            return "Phim bộ"
        if self.inSharedPlaylistView:
            item = self._music_shared_model.item_at(self._shared_playlist_index)
            if item is None:
                return ""
            tracks = list(item.get("episodes") or [])
            downloaded = sum(1 for track in tracks if self._shared_track_in_library(track))
            total = len(tracks)
            if total:
                return f"{downloaded}/{total} bài đã tải"
            return "Playlist"
        if self.inCollectionView and self._current_page == 3 and self._video_section == "series":
            root = self._series_root_folder() or self._current_library_folder()
            rows = collect_series_videos(root)
            if not rows:
                return "Phim bộ trống"
            seasons = len({int(row.get("season") or 1) for row in rows})
            if seasons > 1:
                return f"{len(rows)} tập · {seasons} mùa"
            return f"{len(rows)} tập"
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
        if self.inMovieDetailView:
            item = self._current_movie_detail_item()
            if item is None:
                return ""
            return str(item.get("image") or item.get("imageSource") or "")
        if self.inSharedSeriesView:
            item = self._video_shared_model.item_at(self._shared_series_index)
            return str(item.get("image") or "") if item else ""
        if self.inSharedPlaylistView:
            item = self._music_shared_model.item_at(self._shared_playlist_index)
            return str(item.get("image") or "") if item else ""
        if not self.inCollectionView:
            return ""
        return find_folder_preview_image(self._current_library_folder())

    @pyqtProperty(str, notify=libraryNavigationChanged)
    def collectionBannerDescription(self) -> str:
        if self.inMovieDetailView:
            item = self._current_movie_detail_item()
            if item is None:
                return ""
            artist = _normalize_artist(str(item.get("artist") or ""))
            if artist:
                return artist
            path = str(item.get("canonical_path") or item.get("path") or "")
            if path:
                display = resolve_display(path, default_title=str(item.get("title") or ""))
                return _normalize_artist(display.get("artist") or "")
            return ""
        if self.inSharedSeriesView or (self.inCollectionView and self._current_page == 3 and self._video_section == "series"):
            root = self._series_root_folder() or self._current_library_folder()
            if self.inSharedSeriesView:
                item = self._video_shared_model.item_at(self._shared_series_index)
                return str(item.get("subtitle") or "").strip() if item else ""
            display = resolve_display(
                str(root.resolve()),
                default_title=root.name,
                default_image=find_folder_preview_image(root),
            )
            artist = str(display.get("artist") or "").strip()
            if artist.lower() in {"", "unknown artist", "video", "unknown"}:
                return ""
            return artist
        return ""

    @pyqtProperty(list, notify=libraryNavigationChanged)
    def collectionSeasons(self) -> list:
        if not self.inSharedSeriesView and not (
            self.inCollectionView and self._current_page == 3 and self._video_section == "series"
        ):
            return []
        seasons = {
            int(item.get("season") or 1)
            for item in self._collection_media_items()
            if item is not None
        }
        return sorted(seasons)

    @pyqtProperty(str, notify=primaryPlayLabelChanged)
    def collectionPrimaryPlayLabel(self) -> str:
        if self.inMovieDetailView:
            item = self._current_movie_detail_item()
            if item is None:
                return "Phát"
            if self.movieDetailIsShared:
                if item.get("download_status") != "done" and not self._shared_item_in_library(item):
                    if item.get("is_downloading"):
                        return "Đang tải..."
                    return "Tải xuống"
            if self._is_playing and self._path_matches_item(self._current_path, item):
                return "Tạm dừng"
            return "Phát"
        if not self.use_series_detail_context():
            return "Phát"
        if self._is_playing and self._current_path_in_collection():
            return "Tạm dừng"
        resume = self._resume_item_in_collection(self._detail_playable_items())
        if resume:
            episode = int(resume.get("episode") or 0)
            if episode > 0:
                return f"Tiếp tục Tập {episode}"
            return "Tiếp tục xem"
        return "Phát"

    def use_series_detail_context(self) -> bool:
        return self.inCollectionView or self.inSharedSeriesView

    def _detail_playable_items(self) -> list[dict]:
        if self.inSharedSeriesView:
            series = self._video_shared_model.item_at(self._shared_series_index)
            if series is None:
                return []
            episodes = self._shared_series_episode_items(series)
            return [
                ep for ep in episodes
                if ep.get("download_status") == "done" or self._episode_in_library(ep)
            ]
        if self.inSharedPlaylistView:
            playlist = self._music_shared_model.item_at(self._shared_playlist_index)
            if playlist is None:
                return []
            tracks = self._shared_playlist_track_items(playlist)
            return [
                track for track in tracks
                if track.get("download_status") == "done" or self._shared_track_in_library(track)
            ]
        return self._collection_media_items()

    def _current_path_under(self, directory: Path) -> bool:
        if not self._current_path or _is_remote(self._current_path):
            return False
        try:
            current = Path(self._current_path).resolve()
            root = directory.resolve()
            return root == current or root in current.parents
        except OSError:
            return False

    def _path_matches_item(self, path: str, item: dict) -> bool:
        if not path or item is None:
            return False
        item_path = str(item.get("path") or item.get("url") or "")
        if not item_path:
            return False
        if path == item_path:
            return True
        try:
            return str(Path(path).resolve()) == str(Path(item_path).resolve())
        except OSError:
            return False

    def _current_path_in_collection(self) -> bool:
        if not self._current_path:
            return False
        return self._resume_item_in_collection(self._detail_playable_items()) is not None

    def _resume_item_in_collection(self, items: list[dict]) -> dict | None:
        if not self._current_path or not items:
            return None
        for item in items:
            if self._path_matches_item(self._current_path, item):
                return item
        return None

    @pyqtProperty(bool, notify=libraryNavigationChanged)
    def collectionHasPlayableTracks(self) -> bool:
        if self.inMovieDetailView:
            item = self._current_movie_detail_item()
            if item is None:
                return False
            if self.movieDetailIsShared:
                return (
                    item.get("download_status") == "done"
                    or self._shared_item_in_library(item)
                    or bool(item.get("is_downloading"))
                )
            return bool(str(item.get("path") or "").strip())
        if self.inSharedSeriesView:
            item = self._video_shared_model.item_at(self._shared_series_index)
            if item is None:
                return False
            return any(self._episode_in_library(ep) for ep in item.get("episodes") or [])
        if self.inSharedPlaylistView:
            item = self._music_shared_model.item_at(self._shared_playlist_index)
            if item is None:
                return False
            return any(self._shared_track_in_library(track) for track in item.get("episodes") or [])
        return bool(self._collection_media_items())

    @pyqtProperty(bool, notify=libraryNavigationChanged)
    def collectionCanShuffleOrder(self) -> bool:
        return self._can_shuffle_collection_order()

    @pyqtProperty(bool, notify=playlistOrderUndoChanged)
    def collectionOrderCanUndo(self) -> bool:
        key = self._playlist_order_folder_key()
        return key is not None and key in self._playlist_order_undo

    def set_engine(self, engine) -> None:
        self._engine = engine

    # ── Slots ──

    @pyqtSlot(int)
    @pyqtSlot(int, bool)
    def setCurrentPage(self, page: int, rescan: bool = False) -> None:
        if page != 2 and self._current_page == 2:
            self._music_folder_stack.clear()
            self.libraryNavigationChanged.emit()
        if page != 3 and self._current_page == 3:
            self._video_folder_stack.clear()
            self.libraryNavigationChanged.emit()
        if page == 2:
            if rescan:
                self._load_music_library(refresh=True)
            else:
                self._ensure_music_library_loaded()
            self._sync_library_page_view(2)
        elif page == 3:
            if rescan or self._downloads_active() or self._pending_video_downloads > 0:
                self._load_video_library(refresh=True)
            else:
                self._ensure_video_library_loaded()
            self._sync_library_page_view(3)
        if self._current_page != page:
            prev_page = self._current_page
            self._current_page = page
            titles = {
                2: "Music",
                3: "Videos",
                4: "Tải xuống",
                5: "Cài đặt",
                6: "Podcast",
                7: "Book",
            }
            self._page_title = titles.get(page, "Liminal")
            self.pageTitleChanged.emit()
            self.currentPageChanged.emit()
            self.libraryNavigationChanged.emit()
            if prev_page == 2 or page == 2:
                self.musicSearchChanged.emit()
            if prev_page == 3 or page == 3:
                self.videoSearchChanged.emit()

    @pyqtSlot(str)
    def setSearchFilter(self, text: str) -> None:
        self._filter = text.strip().lower()
        if self._current_page == 2:
            self._ensure_music_library_loaded()
            if self.inCollectionView:
                active = self._music_albums_model if self._music_section == "albums" else self._music_singles_model
                self._apply_library_filter(self._all_music_items, active)
            else:
                self._sync_music_root_view()
        elif self._current_page == 3:
            self._ensure_video_library_loaded()
            if self.inCollectionView:
                active = self._video_series_model if self._video_section == "series" else self._video_movies_model
                self._apply_library_filter(self._all_video_items, active)
            else:
                self._sync_video_root_view()

    @pyqtSlot(int)
    def playMusicSearch(self, index: int) -> None:
        items = list(self._music_search_model._items)
        item = self._music_search_model.item_at(index)
        if item is None:
            return
        self._music_section = "singles"
        self._music_model.set_items(items)
        self._set_playback_queue(items)
        self._play_item(item)

    @pyqtSlot(int)
    def playVideoSearch(self, index: int) -> None:
        items = list(self._video_search_model._items)
        item = self._video_search_model.item_at(index)
        if item is None:
            return
        self._video_section = "movies"
        self._video_model.set_items(items)
        self._set_playback_queue(items)
        self._play_item(item)

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
        else:
            all_items = [
                it for i in range(model.rowCount())
                if (it := model.item_at(i)) is not None and not it.get("is_collection")
            ]
            if all_items:
                self._set_playback_queue(all_items)
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

    @pyqtSlot(int)
    def playVideoMovie(self, index: int) -> None:
        self._video_section = "movies"
        self._video_model.set_items(self._video_movies_model._items)
        item = self._video_movies_model.item_at(index)
        if item is not None:
            self._set_playback_queue([item])
            self._play_item(item)

    @pyqtSlot(int)
    def openVideoMyMovie(self, index: int) -> None:
        item = self._video_my_movies_model.item_at(index)
        if item is None:
            return
        self._video_section = "movies"
        self._video_model.set_items(self._video_my_movies_model._items)
        self._movie_detail_index = index
        self._shared_movie_detail_index = -1
        self.libraryNavigationChanged.emit()

    @pyqtSlot(str, str)
    def enterFocusMode(self, path: str, title: str = "") -> None:
        self._load_focus_subtitles(path)
        episode_list, episode_index, series_key = self._episode_context_for_path(path)
        if series_key != self._current_episode_series_key:
            self._current_episode_list = episode_list
            self._current_episode_series_key = series_key
        self._current_episode_index = episode_index
        self._focus_mode_title = title or Path(path).stem
        self._focus_mode_source = (
            path if path.startswith(("http://", "https://", "file://"))
            else QUrl.fromLocalFile(str(Path(path).expanduser().resolve())).toString()
        )
        # Load saved watch progress
        if not _is_remote(path):
            saved_pos, saved_dur = get_watched_progress(path)
            if saved_pos > 0 and saved_dur > 0:
                self._focus_mode_start_position_ms = int(saved_pos * 1000)
            else:
                self._focus_mode_start_position_ms = 0
        else:
            self._focus_mode_start_position_ms = 0
        self.focusModeStartPositionMsChanged.emit()
        self._in_focus_mode = True
        self._player_bar_visible = False
        self._video_progress_timer.start()
        self.videoStateChanged.emit()
        self.focusModeChanged.emit()
        self.playerBarVisibleChanged.emit()
        # Video playback always starts in fullscreen. QML owns the actual
        # window operation and reacts to this signal in main.qml.
        if not self._is_full_screen:
            self._is_full_screen = True
            self.fullScreenChanged.emit()
        # FocusModeScreen uses Qt Multimedia's portable QML backend.

    def _load_focus_subtitles(self, path: str) -> None:
        self._subtitle_cues = []
        self._subtitle_available = False
        self._subtitle_index = 0
        if not path or _is_remote(path):
            self.videoStateChanged.emit()
            return

        source_path = QUrl(path).toLocalFile() if path.startswith("file:") else path
        video_path = Path(source_path).expanduser()
        subtitle_paths = find_video_subtitle_paths(video_path)
        if not subtitle_paths:
            self.videoStateChanged.emit()
            return

        try:
            text = Path(subtitle_paths[0]).read_text(encoding="utf-8-sig")
            self._subtitle_cues = [
                {
                    "start_ms": max(0, int(cue.start.total_seconds() * 1000)),
                    "end_ms": max(0, int(cue.end.total_seconds() * 1000)),
                    "text": cue.content.strip(),
                }
                for cue in srt.parse(text)
                if cue.content.strip() and cue.end > cue.start
            ]
            self._subtitle_available = bool(self._subtitle_cues)
        except (OSError, UnicodeError, ValueError):
            self._subtitle_cues = []
            self._subtitle_available = False
        self.videoStateChanged.emit()

    def _episode_context_for_path(self, path: str) -> tuple[list[dict], int, str]:
        if not path:
            return [], -1, ""

        candidates: list[Path] = []
        if self.inSharedSeriesView:
            series = self._video_shared_model.item_at(self._shared_series_index)
            if series is not None:
                items = self._shared_series_episode_items(series)
                playable = [
                    item for item in items
                    if item.get("download_status") == "done" or self._episode_in_library(item)
                ]
                for index, item in enumerate(playable):
                    if self._path_matches_item(path, item):
                        return playable, index, f"shared:{self._shared_series_index}"

        if _is_remote(path):
            return [], -1, ""

        if self._current_page == 3 and self._video_section == "series":
            root = self._series_root_folder()
            if root is not None:
                candidates.append(root)

        for item in self._all_video_series:
            root_value = item.get("path") or ""
            if root_value:
                candidates.append(Path(root_value))

        seen: set[str] = set()
        for root in candidates:
            try:
                root_key = str(root.resolve())
            except OSError:
                root_key = str(root)
            if root_key in seen:
                continue
            seen.add(root_key)
            if not self._current_path_under(root) and not self._path_matches_item(path, {"path": root_key}):
                try:
                    current = Path(path).resolve()
                    if root.resolve() not in current.parents:
                        continue
                except OSError:
                    continue
            items = self._load_video_series_items(root)
            for index, item in enumerate(items):
                if self._path_matches_item(path, item):
                    return items, index, root_key
        return [], -1, ""

    @pyqtSlot()
    def nextVideoEpisode(self) -> None:
        if not self.hasNextEpisode:
            return
        self._current_episode_index += 1
        episode = self._current_episode_list[self._current_episode_index]
        path = str(episode.get("path") or episode.get("url") or "")
        self._set_current_path(path)
        self._current_audio_only = False
        self.enterFocusMode(path, episode.get("title", ""))

    @pyqtSlot()
    def previousVideoEpisode(self) -> None:
        if not self.hasPreviousEpisode:
            return
        self._current_episode_index -= 1
        episode = self._current_episode_list[self._current_episode_index]
        path = str(episode.get("path") or episode.get("url") or "")
        self._set_current_path(path)
        self._current_audio_only = False
        self.enterFocusMode(path, episode.get("title", ""))

    @pyqtSlot(int)
    def playEpisodeAtIndex(self, index: int) -> None:
        if index < 0 or index >= len(self._current_episode_list):
            return
        episode = self._current_episode_list[index]
        path = str(episode.get("path") or episode.get("url") or "")
        if not path:
            return
        self._current_episode_index = index
        self._set_current_path(path)
        self._current_audio_only = False
        self.enterFocusMode(path, episode.get("title", ""))

    @pyqtSlot()
    def toggleFullScreen(self) -> None:
        self._is_full_screen = not self._is_full_screen
        self.fullScreenChanged.emit()

    @pyqtSlot(bool)
    def onVideoPlaybackStateChanged(self, is_playing: bool) -> None:
        self._video_is_playing = is_playing
        self.videoStateChanged.emit()

    @pyqtSlot(int)
    def onVideoPositionChanged(self, position_ms: int) -> None:
        self._video_position = position_ms
        self.videoStateChanged.emit()

    @pyqtSlot(int)
    def onVideoDurationChanged(self, duration_ms: int) -> None:
        self._video_duration = duration_ms
        self.videoStateChanged.emit()

    @pyqtSlot()
    def exitFocusMode(self) -> None:
        self._save_video_progress()
        self._video_progress_timer.stop()
        self._in_focus_mode = False
        self._focus_mode_title = ""
        self._focus_mode_source = ""
        self._focus_mode_start_position_ms = 0
        self._current_episode_list = []
        self._current_episode_index = -1
        self._current_episode_series_key = ""
        self._subtitle_cues = []
        self._subtitle_available = False
        self._subtitle_index = 0
        self._player_bar_visible = self._player_bar_always_visible
        self.videoStateChanged.emit()
        self.focusModeChanged.emit()
        self.playerBarVisibleChanged.emit()
        if self._is_full_screen:
            self._is_full_screen = False
            self.fullScreenChanged.emit()

    def _save_video_progress(self) -> None:
        """Persist current video watch progress to metadata store."""
        if (
            not self._in_focus_mode
            or not self._current_path
            or _is_remote(self._current_path)
            or self._video_duration <= 0
        ):
            return
        set_watched_progress(
            self._current_path,
            position=self._video_position / 1000.0,
            duration=self._video_duration / 1000.0,
        )

    @pyqtSlot(int)
    def playVideoMyMovie(self, index: int) -> None:
        self._video_section = "movies"
        self._video_model.set_items(self._video_my_movies_model._items)
        item = self._video_my_movies_model.item_at(index)
        if item is not None:
            self._set_playback_queue([item])
            self._play_item(item)

    @pyqtSlot()
    def playMovieDetail(self) -> None:
        if self._shared_movie_detail_index >= 0:
            item = self._video_shared_model.item_at(self._shared_movie_detail_index)
            if item is None:
                return
            if item.get("download_status") != "done" and not self._shared_item_in_library(item):
                self.downloadSharedItem(self._shared_movie_detail_index)
                return
            self._play_shared_movie_item(item)
            return
        if self._movie_detail_index >= 0:
            self.playVideoMyMovie(self._movie_detail_index)

    def _play_shared_movie_item(self, item: dict) -> None:
        play_item = dict(item)
        track_id = str(item.get("track_id") or "")
        local_path = self._find_video_path_by_source_id(track_id)
        if local_path:
            play_item["path"] = local_path
            play_item["is_remote"] = False

        self._video_section = "shared"
        self._video_model.set_items(self._video_shared_model._items)
        self._set_playback_queue([play_item])
        self._play_item(play_item)

    @pyqtSlot(int)
    def openVideoSeries(self, index: int) -> None:
        self._video_section = "series"
        self.openCollection(index)

    def library_share_info(self, path: str) -> dict | None:
        """Build share payload from a library file (title, author, source URL, thumbnail)."""
        resolved = _resolve_metadata_path(path)
        if not resolved or resolved.startswith("__liminal__:"):
            return None

        file_path = Path(resolved)
        if not file_path.is_file():
            return None

        meta_path = str(file_path.resolve())
        thumb = read_video_thumbnail(file_path)
        display = resolve_display(
            meta_path,
            default_title=file_path.stem,
            default_image=thumb,
        )
        source_url = resolve_source_url(meta_path)
        thumbnail_url = ""
        yt_id = extract_youtube_id(source_url) or extract_youtube_id(resolve_source_id(meta_path))
        if yt_id:
            thumbnail_url = f"https://i.ytimg.com/vi/{yt_id}/hqdefault.jpg"
        else:
            stored_thumb = str(get_metadata(meta_path).get("thumbnail_url") or "").strip()
            if stored_thumb.startswith(("http://", "https://")):
                thumbnail_url = stored_thumb

        return {
            "title": display["title"],
            "author": display["artist"],
            "source_url": source_url,
            "thumbnail_url": thumbnail_url,
        }

    def library_music_share_info(self, path: str) -> dict | None:
        """Build share payload from a music file (title, artist, source URL, thumbnail)."""
        resolved = _resolve_metadata_path(path)
        if not resolved or resolved.startswith("__liminal__:"):
            return None

        file_path = Path(resolved)
        if not file_path.is_file() or file_path.suffix.lower() not in AUDIO_EXTS:
            return None

        meta_path = str(file_path.resolve())
        display = resolve_display(
            meta_path,
            default_title=file_path.stem,
            default_image="",
        )
        image = display["image"] or ""
        if not image:
            embedded = read_embedded_metadata(file_path)
            image = str(embedded.get("image") or "").strip()

        source_url = resolve_source_url(meta_path)
        thumbnail_url = ""
        yt_id = extract_youtube_id(source_url) or extract_youtube_id(resolve_source_id(meta_path))
        if yt_id:
            thumbnail_url = f"https://i.ytimg.com/vi/{yt_id}/hqdefault.jpg"
        elif image.startswith(("http://", "https://")):
            thumbnail_url = image
        else:
            stored_thumb = str(get_metadata(meta_path).get("thumbnail_url") or "").strip()
            if stored_thumb.startswith(("http://", "https://")):
                thumbnail_url = stored_thumb

        return {
            "title": display["title"],
            "author": display["artist"],
            "source_url": source_url,
            "thumbnail_url": thumbnail_url,
        }

    @pyqtProperty(str, notify=libraryNavigationChanged)
    def currentSeriesFolderPath(self) -> str:
        if self._current_page != 3 or not self.inCollectionView or self._video_section != "series":
            return ""
        try:
            return str((self._series_root_folder() or self._current_library_folder()).resolve())
        except OSError:
            return str(self._series_root_folder() or self._current_library_folder())

    @pyqtProperty(str, notify=libraryNavigationChanged)
    def currentPlaylistFolderPath(self) -> str:
        if self._current_page != 2 or not self.inCollectionView or self._music_section != "albums":
            return ""
        stack = self._music_folder_stack
        if not stack or self._is_all_musics_virtual(stack[-1].path):
            return ""
        try:
            return str(self._current_library_folder().resolve())
        except OSError:
            return str(self._current_library_folder())

    def library_series_share_info(self, path: str) -> dict | None:
        """Build a series share payload from a video collection folder."""
        from src import share_manager

        resolved = _resolve_metadata_path(path)
        if not resolved or resolved.startswith("__liminal__:"):
            return None

        folder = Path(resolved)
        if not folder.is_dir():
            return None

        episodes = [
            episode_share_payload(row)
            for row in collect_series_videos(folder)
            if share_manager.is_allowed_share_url(str(row.get("source_url") or ""))
        ]
        for index, episode in enumerate(episodes, start=1):
            episode["index"] = index

        if not episodes:
            return None

        folder_display = resolve_display(
            str(folder.resolve()),
            default_title=folder.name,
            default_image=find_folder_preview_image(folder),
        )
        thumbnail_url = folder_display["image"] or ""
        if thumbnail_url and not thumbnail_url.startswith(("http://", "https://")):
            yt_id = extract_youtube_id(episodes[0].get("source_url") or "")
            if yt_id:
                thumbnail_url = f"https://i.ytimg.com/vi/{yt_id}/hqdefault.jpg"

        return {
            "title": folder_display["title"],
            "author": folder_display["artist"],
            "thumbnail_url": thumbnail_url if thumbnail_url.startswith(("http://", "https://")) else "",
            "episodes": episodes,
        }

    def library_playlist_share_info(self, path: str) -> dict | None:
        """Build a playlist share payload from a music album folder."""
        from src import share_manager

        resolved = _resolve_metadata_path(path)
        if not resolved or resolved.startswith("__liminal__:"):
            return None

        folder = Path(resolved)
        if not folder.is_dir():
            return None

        tracks = [
            track_share_payload(row)
            for row in collect_playlist_tracks(folder)
            if share_manager.is_allowed_share_url(str(row.get("source_url") or ""))
        ]
        for index, track in enumerate(tracks, start=1):
            track["index"] = index

        if not tracks:
            return None

        folder_display = resolve_display(
            str(folder.resolve()),
            default_title=folder.name,
            default_image=find_folder_preview_image(folder),
        )
        thumbnail_url = folder_display["image"] or ""
        if thumbnail_url and not thumbnail_url.startswith(("http://", "https://")):
            yt_id = extract_youtube_id(tracks[0].get("source_url") or "")
            if yt_id:
                thumbnail_url = f"https://i.ytimg.com/vi/{yt_id}/hqdefault.jpg"

        return {
            "title": folder_display["title"],
            "author": folder_display["artist"],
            "thumbnail_url": thumbnail_url if thumbnail_url.startswith(("http://", "https://")) else "",
            "tracks": tracks,
        }

    @pyqtSlot(int)
    def playVideoShared(self, index: int) -> None:
        item = self._video_shared_model.item_at(index)
        if item is None:
            return
        if item.get("is_series"):
            self.openVideoSharedSeries(index)
            return
        self.openVideoSharedMovie(index)

    @pyqtSlot(int)
    def openVideoSharedMovie(self, index: int) -> None:
        item = self._video_shared_model.item_at(index)
        if item is None or item.get("is_series"):
            return
        self._video_section = "shared"
        self._shared_movie_detail_index = index
        self._movie_detail_index = -1
        self.libraryNavigationChanged.emit()

    def _series_root_folder(self) -> Path | None:
        stack = self._video_folder_stack
        return stack[0].path if stack else None

    def _episode_row_to_media_item(self, row: dict, index: int) -> dict:
        path = str(row.get("path") or "")
        season = int(row.get("season") or 1)
        episode = int(row.get("episode") or 1)
        return {
            "title": str(row.get("title") or f"Tập {episode}"),
            "subtitle": str(row.get("subtitle") or format_episode_subtitle(season=season, episode=episode)),
            "artist": _normalize_artist(str(row.get("artist") or "")),
            "path": path,
            "canonical_path": path,
            "url": path,
            "track_id": path,
            "duration": "",
            "image": str(row.get("image") or ""),
            "accent": ACCENT_COLORS[index % len(ACCENT_COLORS)],
            "audio_only": False,
            "is_remote": False,
            "is_collection": False,
            "kind": "file",
            "child_count": 0,
            "preview_images": [],
            "season": season,
            "episode": episode,
            "download_percent": 0.0,
            "download_status": "",
            "is_downloading": False,
            "watched_percent": _compute_watched_percent(path),
        }

    def _load_video_series_items(self, folder: Path) -> list[dict]:
        root = self._series_root_folder() or folder
        rows = collect_series_videos(root)
        return [self._episode_row_to_media_item(row, index) for index, row in enumerate(rows)]

    @pyqtSlot(result=list)
    def currentSeriesSetupRows(self) -> list:
        if self._current_page != 3 or not self.inCollectionView or self._video_section != "series":
            return []
        root = self._series_root_folder() or self._current_library_folder()
        return collect_series_videos(root)

    @pyqtSlot(result=list)
    def autoDetectSeriesSetupRows(self) -> list:
        if self._current_page != 3 or not self.inCollectionView or self._video_section != "series":
            return []
        root = self._series_root_folder() or self._current_library_folder()
        return detect_series_rows(root)

    @pyqtSlot(list)
    def saveSeriesSetupRows(self, rows: list) -> None:
        if not rows:
            return
        save_series_rows([dict(row) for row in rows if isinstance(row, dict)])
        self._reload_library_view(3)

    @pyqtProperty(bool, notify=seriesAiSortLoadingChanged)
    def seriesAiSortLoading(self) -> bool:
        return self._series_ai_loading

    def _set_series_ai_loading(self, loading: bool) -> None:
        if self._series_ai_loading == loading:
            return
        self._series_ai_loading = loading
        self.seriesAiSortLoadingChanged.emit()

    @pyqtSlot()
    def requestAiSeriesSort(self) -> None:
        asyncio.create_task(self._request_ai_series_sort())

    async def _request_ai_series_sort(self) -> None:
        if self._current_page != 3 or not self.inCollectionView or self._video_section != "series":
            self.seriesAiSortError.emit("Mở phim bộ để dùng AI sắp xếp.")
            return
        root = self._series_root_folder() or self._current_library_folder()
        rows = collect_series_videos(root)
        if not rows:
            self.seriesAiSortError.emit("Không có tập nào để sắp xếp.")
            return
        title = self.collectionBannerTitle or root.name
        self._set_series_ai_loading(True)
        try:
            from src import share_manager

            sorted_rows = await share_manager.ai_sort_series_episodes(
                series_title=title,
                rows=rows,
            )
            self.seriesAiSortFinished.emit(sorted_rows)
        except ValueError as exc:
            self.seriesAiSortError.emit(str(exc))
        except Exception:
            logger.exception("AI series sort failed")
            self.seriesAiSortError.emit("AI sắp xếp thất bại.")
        finally:
            self._set_series_ai_loading(False)

    @pyqtSlot(list)
    def saveTapOrderAssignments(self, assignments: list) -> None:
        if self._current_page != 3 or not self.inCollectionView or self._video_section != "series":
            return
        payload = [dict(row) for row in assignments if isinstance(row, dict)]
        if not payload:
            return
        root = self._series_root_folder() or self._current_library_folder()
        rows = collect_series_videos(root)
        updated = apply_tap_assignments(rows, payload)
        save_series_rows(updated)
        self._reload_library_view(3)

    @pyqtSlot(list, int)
    def saveTapOrderRows(self, ordered_paths: list, season: int) -> None:
        if self._current_page != 3 or not self.inCollectionView or self._video_section != "series":
            return
        paths = [str(path).strip() for path in ordered_paths if str(path).strip()]
        if not paths:
            return
        root = self._series_root_folder() or self._current_library_folder()
        rows = collect_series_videos(root)
        updated = apply_tap_order(rows, paths, season=max(1, int(season)))
        save_series_rows(updated)
        self._reload_library_view(3)

    @pyqtSlot(str, str, int, int)
    def editSeriesEpisodeMetadata(self, path: str, title: str, season: int, episode: int) -> None:
        value = _resolve_metadata_path(path)
        if not value:
            return
        set_metadata(
            value,
            title=title.strip(),
            season=str(max(1, int(season))),
            episode=str(max(1, int(episode))),
        )
        self._reload_library_view(3)

    def _find_video_path_by_source_id(self, source_id: str) -> str:
        needle = (source_id or "").strip()
        if not needle:
            return ""
        self._ensure_video_library_loaded()
        if self._video_track_infos is not None:
            for info in self._video_track_infos:
                if resolve_source_id(info.path) == needle:
                    return info.path
        for item in self._all_video_tracks:
            path = str(item.get("path") or "")
            if path and resolve_source_id(path) == needle:
                return path
        return ""

    @pyqtSlot(int)
    def downloadSharedItem(self, index: int) -> None:
        item = self._video_shared_model.item_at(index)
        if item is None:
            return
        if item.get("is_series"):
            self.openVideoSharedSeries(index)
            return
        if self._shared_item_in_library(item):
            return
        source_url = str(item.get("url") or "").strip()
        if not source_url:
            self.downloadError.emit("", "Mục chia sẻ thiếu link tải.")
            return
        self._mark_shared_downloading(item, percent=0.0)
        self.downloadMedia(source_url, "video", "")

    @pyqtSlot(int)
    def openVideoSharedSeries(self, index: int) -> None:
        item = self._video_shared_model.item_at(index)
        if item is None or not item.get("is_series"):
            return
        raw = self._find_shared_series_raw(str(item.get("share_id") or ""))
        if raw is not None:
            item = {**item, "episodes": list(raw.get("episodes") or [])}
            self._all_video_shared[index] = self._shared_item_to_model(
                {**raw, **item},
                index,
            )
        self._shared_series_index = index
        self._video_section = "shared"
        model_item = self._video_shared_model.item_at(index) or item
        episodes = self._shared_series_episode_items(model_item)
        self._video_model.set_items(episodes)
        self.libraryNavigationChanged.emit()

    @pyqtSlot()
    def goBackSharedSeries(self) -> None:
        if self._shared_series_index < 0:
            return
        self._shared_series_index = -1
        self.libraryNavigationChanged.emit()

    @pyqtSlot(int)
    def playSharedSeriesEpisode(self, index: int) -> None:
        if self._shared_series_index < 0:
            return
        series = self._video_shared_model.item_at(self._shared_series_index)
        if series is None:
            return
        episodes = self._shared_series_episode_items(series)
        if index < 0 or index >= len(episodes):
            return
        item = episodes[index]
        if item.get("download_status") != "done" and not self._episode_in_library(item):
            return
        play_item = dict(item)
        track_id = str(item.get("track_id") or "")
        local_path = self._find_video_path_by_source_id(track_id)
        if local_path:
            play_item["path"] = local_path
            play_item["is_remote"] = False
        playable = [
            ep for ep in episodes
            if ep.get("download_status") == "done" or self._episode_in_library(ep)
        ]
        self._video_section = "shared"
        self._video_model.set_items(episodes)
        self._set_playback_queue(playable)
        self._play_item(play_item)

    @pyqtSlot(int)
    def downloadSharedSeriesEpisode(self, index: int) -> None:
        if self._shared_series_index < 0:
            return
        series = self._video_shared_model.item_at(self._shared_series_index)
        if series is None:
            return
        episodes = list(series.get("episodes") or [])
        if index < 0 or index >= len(episodes):
            return
        episode = episodes[index]
        if self._episode_in_library(episode):
            return
        folder = self._series_download_folder(series, episode)
        self._queue_shared_episode_download(series, episode, folder)

    def queueInitialSharedSeriesDownloads(self, share_id: str) -> None:
        series = self._find_shared_series_raw(share_id)
        if series is None:
            return
        from src import share_manager

        folder = self._series_download_folder(series)
        for episode in share_manager.initial_series_download_episodes(list(series.get("episodes") or [])):
            if self._episode_in_library(episode):
                continue
            status = str(episode.get("download_status") or "pending")
            if status == "downloading":
                continue
            ep_folder = self._series_download_folder(series, episode)
            self._queue_shared_episode_download(series, episode, ep_folder)

    @pyqtSlot(int)
    def playMusicShared(self, index: int) -> None:
        item = self._music_shared_model.item_at(index)
        if item is None:
            return
        if item.get("is_playlist"):
            self.openMusicSharedPlaylist(index)
            return
        if self._shared_music_item_in_library(item):
            self._play_shared_music_item(item)
            return
        self.downloadMusicSharedItem(index)

    @pyqtSlot(int)
    def downloadMusicSharedItem(self, index: int) -> None:
        item = self._music_shared_model.item_at(index)
        if item is None:
            return
        if item.get("is_playlist"):
            self.openMusicSharedPlaylist(index)
            return
        if self._shared_music_item_in_library(item):
            return
        source_url = str(item.get("url") or "").strip()
        if not source_url:
            self.downloadError.emit("", "Mục chia sẻ thiếu link tải.")
            return
        self._mark_music_shared_downloading(item, percent=0.0)
        self.downloadMedia(source_url, "music", "")

    def _play_shared_music_item(self, item: dict) -> None:
        play_item = dict(item)
        track_id = str(item.get("track_id") or "")
        local_path = self._find_music_path_by_source_id(track_id)
        if local_path:
            play_item["path"] = local_path
            play_item["is_remote"] = False
            play_item["audio_only"] = True
        self._music_model.set_items([play_item])
        self._set_playback_queue([play_item])
        self._play_item(play_item)

    @pyqtSlot(int)
    def openMusicSharedPlaylist(self, index: int) -> None:
        item = self._music_shared_model.item_at(index)
        if item is None or not item.get("is_playlist"):
            return
        raw = self._find_shared_playlist_raw(str(item.get("share_id") or ""))
        if raw is not None:
            item = {**item, "episodes": list(raw.get("episodes") or [])}
            self._all_music_shared[index] = self._shared_item_to_model(
                {**raw, **item},
                index,
                pool="music",
            )
        self._shared_playlist_index = index
        model_item = self._music_shared_model.item_at(index) or item
        self._music_model.set_items(self._shared_playlist_track_items(model_item))
        self.libraryNavigationChanged.emit()

    @pyqtSlot()
    def goBackSharedPlaylist(self) -> None:
        if self._shared_playlist_index < 0:
            return
        self._shared_playlist_index = -1
        self.libraryNavigationChanged.emit()

    @pyqtSlot(int)
    def playSharedPlaylistTrack(self, index: int) -> None:
        if self._shared_playlist_index < 0:
            return
        playlist = self._music_shared_model.item_at(self._shared_playlist_index)
        if playlist is None:
            return
        tracks = self._shared_playlist_track_items(playlist)
        if index < 0 or index >= len(tracks):
            return
        item = tracks[index]
        if item.get("download_status") != "done" and not self._shared_track_in_library(item):
            return
        play_item = dict(item)
        track_id = str(item.get("track_id") or "")
        local_path = self._find_music_path_by_source_id(track_id)
        if local_path:
            play_item["path"] = local_path
            play_item["is_remote"] = False
        playable = [
            track for track in tracks
            if track.get("download_status") == "done" or self._shared_track_in_library(track)
        ]
        self._music_model.set_items(tracks)
        self._set_playback_queue(playable)
        self._play_item(play_item)

    @pyqtSlot(int)
    def downloadSharedPlaylistTrack(self, index: int) -> None:
        if self._shared_playlist_index < 0:
            return
        playlist = self._music_shared_model.item_at(self._shared_playlist_index)
        if playlist is None:
            return
        tracks = list(playlist.get("episodes") or [])
        if index < 0 or index >= len(tracks):
            return
        track = tracks[index]
        if self._shared_track_in_library(track):
            return
        folder = self._playlist_download_folder(playlist)
        self._queue_shared_track_download(playlist, track, folder)

    def queueInitialSharedPlaylistDownloads(self, share_id: str) -> None:
        playlist = self._find_shared_playlist_raw(share_id)
        if playlist is None:
            return
        from src import share_manager

        folder = self._playlist_download_folder(playlist)
        for track in share_manager.initial_playlist_download_tracks(list(playlist.get("episodes") or [])):
            if self._shared_track_in_library(track):
                continue
            status = str(track.get("download_status") or "pending")
            if status == "downloading":
                continue
            self._queue_shared_track_download(playlist, track, folder)

    def apply_shared_items(self, items: list[dict]) -> None:
        """Convert API/cache rows into shared video and music models."""
        self._ensure_source_ids("video")
        self._ensure_source_ids("music")

        video_items: list[dict] = []
        music_items: list[dict] = []
        for item in items:
            media_type = str(item.get("media_type") or "video").strip().lower()
            if media_type == "series":
                if not self._shared_series_in_library(item):
                    video_items.append(item)
                continue
            if media_type == "playlist":
                if not self._shared_playlist_in_library(item):
                    music_items.append(item)
                continue
            if media_type == "music":
                if not self._shared_music_item_in_library({
                    "track_id": str(item.get("video_id") or ""),
                    "url": str(item.get("source_url") or item.get("url") or ""),
                }):
                    music_items.append(item)
                continue
            if not self._shared_item_in_library({
                "track_id": str(item.get("video_id") or ""),
                "url": str(item.get("source_url") or item.get("url") or ""),
            }):
                video_items.append(item)

        self._all_video_shared = [
            self._shared_item_to_model(item, index, pool="video")
            for index, item in enumerate(video_items)
        ]
        self._all_music_shared = [
            self._shared_item_to_model(item, index, pool="music")
            for index, item in enumerate(music_items)
        ]
        self._apply_library_filter(self._all_video_shared, self._video_shared_model)
        self._apply_library_filter(self._all_music_shared, self._music_shared_model)

    @pyqtSlot(int)
    def dismissSharedItem(self, index: int) -> None:
        item = self._video_shared_model.item_at(index)
        if item is None:
            return
        share_id = str(item.get("share_id") or "").strip()
        if not share_id:
            return
        asyncio.create_task(self._dismiss_shared_item(share_id))

    @pyqtSlot(int)
    def dismissMusicSharedItem(self, index: int) -> None:
        item = self._music_shared_model.item_at(index)
        if item is None:
            return
        share_id = str(item.get("share_id") or "").strip()
        if not share_id:
            return
        asyncio.create_task(self._dismiss_shared_item(share_id))

    async def _dismiss_shared_item(self, share_id: str) -> None:
        from src import share_manager

        try:
            items = await share_manager.dismiss_share(share_id)
            self.apply_shared_items(items)
        except ValueError as exc:
            self.downloadError.emit("", str(exc))
        except Exception:
            logger.exception("Dismiss shared item failed")
            self.downloadError.emit("", "Không thể xóa mục chia sẻ.")

    def _remove_shared_item_by_id(self, share_id: str) -> None:
        needle = (share_id or "").strip()
        if not needle:
            return
        self._all_video_shared = [
            item for item in self._all_video_shared
            if str(item.get("share_id") or "") != needle
        ]
        self._all_music_shared = [
            item for item in self._all_music_shared
            if str(item.get("share_id") or "") != needle
        ]
        if self._current_page == 3 and not self.inCollectionView and not self.inSharedSeriesView:
            self._apply_library_filter(self._all_video_shared, self._video_shared_model)
        if self._current_page == 2 and not self.inCollectionView and not self.inSharedPlaylistView:
            self._apply_library_filter(self._all_music_shared, self._music_shared_model)

    async def _dismiss_shared_after_download(self, share_id: str) -> None:
        from src import share_manager

        try:
            await share_manager.dismiss_share(share_id)
        except Exception:
            logger.warning("Could not dismiss shared item %r after download", share_id, exc_info=True)

    def _shared_item_in_library(self, item: dict) -> bool:
        track_id = str(item.get("track_id") or "").strip()
        if not track_id:
            track_id = extract_youtube_id(str(item.get("url") or ""))
        self._ensure_source_ids("video")
        return bool(track_id and track_id in self._video_source_ids)

    def _shared_music_item_in_library(self, item: dict) -> bool:
        track_id = str(item.get("track_id") or "").strip()
        if not track_id:
            track_id = extract_youtube_id(str(item.get("url") or ""))
        self._ensure_source_ids("music")
        return bool(track_id and track_id in self._music_source_ids)

    def _shared_item_to_model(self, item: dict, index: int, *, pool: str = "video") -> dict:
        media_type = str(item.get("media_type") or "video").strip().lower()
        is_series = media_type == "series"
        is_playlist = media_type == "playlist"
        is_collection = is_series or is_playlist
        episodes = list(item.get("episodes") or [])
        source_url = str(item.get("source_url") or item.get("url") or "").strip()
        video_id = str(item.get("video_id") or "").strip()
        if not video_id:
            video_id = extract_youtube_id(source_url) or str(item.get("id") or "")

        if is_series:
            downloaded = sum(1 for ep in episodes if self._episode_in_library(ep))
            total = len(episodes)
            in_library = total > 0 and downloaded == total
            if in_library:
                download_status = "done"
                download_percent = 100.0
                is_downloading = False
            else:
                active = [
                    ep for ep in episodes
                    if str(ep.get("download_status") or "") == "downloading" or ep.get("is_downloading")
                ]
                download_status = "downloading" if active else str(item.get("download_status") or "pending")
                download_percent = (downloaded / total * 100.0) if total else 0.0
                is_downloading = bool(active)
            subtitle = f"{total} tập" if total else "Phim bộ"
            if total and not in_library:
                subtitle = f"{downloaded}/{total} tập"
        elif is_playlist:
            downloaded = sum(1 for track in episodes if self._shared_track_in_library(track))
            total = len(episodes)
            in_library = total > 0 and downloaded == total
            if in_library:
                download_status = "done"
                download_percent = 100.0
                is_downloading = False
            else:
                active = [
                    track for track in episodes
                    if str(track.get("download_status") or "") == "downloading" or track.get("is_downloading")
                ]
                download_status = "downloading" if active else str(item.get("download_status") or "pending")
                download_percent = (downloaded / total * 100.0) if total else 0.0
                is_downloading = bool(active)
            subtitle = f"{total} bài" if total else "Playlist"
            if total and not in_library:
                subtitle = f"{downloaded}/{total} bài"
        elif pool == "music":
            in_library = self._shared_music_item_in_library({
                "track_id": video_id,
                "url": source_url,
            })
            subtitle = str(item.get("author") or "Chia sẻ")
            if in_library:
                download_status = "done"
                download_percent = 100.0
                is_downloading = False
            else:
                download_status = str(item.get("download_status") or "pending")
                download_percent = float(item.get("download_percent") or 0.0)
                is_downloading = bool(item.get("is_downloading"))
        else:
            in_library = self._shared_item_in_library({
                "track_id": video_id,
                "url": source_url,
            })
            subtitle = str(item.get("author") or "Chia sẻ")
            if in_library:
                download_status = "done"
                download_percent = 100.0
                is_downloading = False
            else:
                download_status = str(item.get("download_status") or "pending")
                download_percent = float(item.get("download_percent") or 0.0)
                is_downloading = bool(item.get("is_downloading"))

        thumb = str(item.get("thumbnail_path") or item.get("thumbnail_url") or "").strip()

        return {
            "title": str(item.get("title") or "Không có tên"),
            "subtitle": subtitle,
            "image": thumb,
            "path": f"__liminal__:share:{item.get('id')}",
            "url": source_url,
            "track_id": video_id,
            "share_id": str(item.get("id") or ""),
            "share_code": str(item.get("code") or ""),
            "audio_only": pool == "music" or media_type == "music",
            "is_remote": True,
            "is_collection": is_collection,
            "is_series": is_series,
            "is_playlist": is_playlist,
            "episodes": episodes,
            "duration": "",
            "accent": ACCENT_COLORS[index % len(ACCENT_COLORS)],
            "download_percent": download_percent,
            "download_status": download_status,
            "is_downloading": is_downloading,
            "in_library": in_library,
            "child_count": len(episodes) if is_collection else 0,
        }

    def _episode_in_library(self, episode: dict) -> bool:
        source_url = str(episode.get("source_url") or episode.get("url") or "").strip()
        track_id = extract_youtube_id(source_url) or source_url
        if not track_id:
            return False
        self._ensure_source_ids("video")
        if track_id in self._video_source_ids:
            return True
        return bool(self._find_video_path_by_source_id(track_id))

    def _shared_series_in_library(self, item: dict) -> bool:
        episodes = list(item.get("episodes") or [])
        if not episodes:
            return False
        return all(self._episode_in_library(ep) for ep in episodes)

    def _shared_track_in_library(self, track: dict) -> bool:
        source_url = str(track.get("source_url") or track.get("url") or "").strip()
        track_id = extract_youtube_id(source_url) or source_url
        if not track_id:
            return False
        self._ensure_source_ids("music")
        if track_id in self._music_source_ids:
            return True
        return bool(self._find_music_path_by_source_id(track_id))

    def _shared_playlist_in_library(self, item: dict) -> bool:
        tracks = list(item.get("episodes") or [])
        if not tracks:
            return False
        return all(self._shared_track_in_library(track) for track in tracks)

    def _find_music_path_by_source_id(self, source_id: str) -> str:
        needle = (source_id or "").strip()
        if not needle:
            return ""
        self._ensure_music_library_loaded()
        if self._music_track_infos is not None:
            for info in self._music_track_infos:
                if resolve_source_id(info.path) == needle:
                    return info.path
        for item in self._all_music_tracks:
            path = str(item.get("path") or "")
            if path and resolve_source_id(path) == needle:
                return path
        return ""

    def _playlist_download_folder(self, playlist: dict) -> str:
        title = str(playlist.get("title") or "Playlist").strip() or "Playlist"
        return playlist_download_subdir(title)

    def _shared_playlist_track_items(self, playlist: dict) -> list[dict]:
        share_id = str(playlist.get("share_id") or playlist.get("id") or "")
        playlist_title = str(playlist.get("title") or "Playlist")
        tracks = list(playlist.get("episodes") or [])
        tracks.sort(key=lambda track: int(track.get("index") or track.get("episode") or 0))
        items: list[dict] = []
        for index, track in enumerate(tracks):
            source_url = str(track.get("source_url") or "").strip()
            track_id = extract_youtube_id(source_url) or source_url
            in_library = self._shared_track_in_library(track)
            if in_library:
                download_status = "done"
                download_percent = 100.0
                is_downloading = False
            else:
                download_status = str(track.get("download_status") or "pending")
                download_percent = float(track.get("download_percent") or 0.0)
                is_downloading = bool(track.get("is_downloading"))
            local_path = self._find_music_path_by_source_id(track_id)
            track_no = int(track.get("index") or track.get("episode") or index + 1)
            items.append({
                "title": str(track.get("title") or f"Bài {track_no}"),
                "subtitle": playlist_title,
                "artist": playlist_title,
                "image": str(track.get("thumbnail_url") or playlist.get("image") or ""),
                "path": local_path or f"__liminal__:share_track:{share_id}:{track.get('index') or index + 1}",
                "url": source_url,
                "track_id": track_id,
                "share_id": share_id,
                "track_index": track_no,
                "audio_only": True,
                "is_remote": not bool(local_path),
                "is_collection": False,
                "is_playlist": False,
                "duration": "",
                "accent": ACCENT_COLORS[index % len(ACCENT_COLORS)],
                "download_percent": download_percent,
                "download_status": download_status,
                "is_downloading": is_downloading,
                "in_library": in_library,
            })
        return items

    def _find_shared_playlist_raw(self, share_id: str) -> dict | None:
        needle = (share_id or "").strip()
        if not needle:
            return None
        from src import share_manager

        for item in share_manager.get_cached_items():
            if str(item.get("id") or "") == needle:
                return item
        for item in self._all_music_shared:
            if str(item.get("share_id") or "") == needle:
                return item
        return None

    def _queue_shared_track_download(self, playlist: dict, track: dict, folder: str) -> None:
        source_url = str(track.get("source_url") or "").strip()
        if not source_url or self._shared_track_in_library(track):
            return
        track["is_downloading"] = True
        track["download_status"] = "downloading"
        track["download_percent"] = float(track.get("download_percent") or 0.0)
        self._persist_shared_playlist_state(playlist)
        self._refresh_shared_playlist_model(playlist)
        self.downloadMedia(source_url, "music", folder)

    def _persist_shared_playlist_state(self, playlist: dict) -> None:
        from src import share_manager

        share_id = str(playlist.get("share_id") or playlist.get("id") or "").strip()
        if not share_id:
            return
        tracks = list(playlist.get("episodes") or [])
        items = share_manager.get_cached_items()
        changed = False
        for item in items:
            if str(item.get("id") or "") != share_id:
                continue
            item["episodes"] = tracks
            changed = True
            break
        if changed:
            from src.share_manager import _read_local_file, _write_local_file
            from src.device_store import get_device_id
            import time

            data = _read_local_file()
            _write_local_file({
                "device_id": data.get("device_id") or get_device_id(),
                "fetched_at": time.time(),
                "items": items,
            })

    def _refresh_shared_playlist_model(self, playlist: dict) -> None:
        share_id = str(playlist.get("share_id") or playlist.get("id") or "")
        raw = self._find_shared_playlist_raw(share_id)
        source = raw or playlist
        for index, item in enumerate(self._all_music_shared):
            if str(item.get("share_id") or "") != share_id:
                continue
            updated = self._shared_item_to_model(
                {**source, **item, "episodes": list(source.get("episodes") or [])},
                index,
                pool="music",
            )
            self._all_music_shared[index] = updated
            if self._current_page == 2 and not self.inCollectionView and self._shared_playlist_index < 0:
                self._apply_library_filter(self._all_music_shared, self._music_shared_model)
            if self._shared_playlist_index >= 0:
                model_item = self._music_shared_model.item_at(self._shared_playlist_index)
                if model_item is not None and str(model_item.get("share_id") or "") == share_id:
                    self._music_model.set_items(self._shared_playlist_track_items(updated))
            self.libraryNavigationChanged.emit()
            break

    def _series_download_folder(self, series: dict, episode: dict | None = None) -> str:
        title = str(series.get("title") or "Phim bộ").strip() or "Phim bộ"
        season = int((episode or {}).get("season") or 1)
        return episode_download_subdir(title, season=season)

    def _shared_series_episode_items(self, series: dict) -> list[dict]:
        share_id = str(series.get("share_id") or series.get("id") or "")
        series_title = str(series.get("title") or "Phim bộ")
        episodes = list(series.get("episodes") or [])
        episodes.sort(key=lambda ep: (
            int(ep.get("season") or 1),
            int(ep.get("episode") or ep.get("index") or 0),
        ))
        items: list[dict] = []
        for index, episode in enumerate(episodes):
            source_url = str(episode.get("source_url") or "").strip()
            track_id = extract_youtube_id(source_url) or source_url
            in_library = self._episode_in_library(episode)
            if in_library:
                download_status = "done"
                download_percent = 100.0
                is_downloading = False
            else:
                download_status = str(episode.get("download_status") or "pending")
                download_percent = float(episode.get("download_percent") or 0.0)
                is_downloading = bool(episode.get("is_downloading"))
            local_path = self._find_video_path_by_source_id(track_id)
            season = int(episode.get("season") or 1)
            episode_no = int(episode.get("episode") or episode.get("index") or index + 1)
            items.append({
                "title": str(episode.get("title") or f"Tập {episode_no}"),
                "subtitle": format_episode_subtitle(season=season, episode=episode_no, extra=series_title),
                "image": str(episode.get("thumbnail_url") or series.get("image") or ""),
                "path": local_path or f"__liminal__:share_ep:{share_id}:{episode.get('index') or index + 1}",
                "url": source_url,
                "track_id": track_id,
                "share_id": share_id,
                "episode_index": episode_no,
                "season": season,
                "episode": episode_no,
                "audio_only": False,
                "is_remote": not bool(local_path),
                "is_collection": False,
                "is_series": False,
                "duration": "",
                "accent": ACCENT_COLORS[index % len(ACCENT_COLORS)],
                "download_percent": download_percent,
                "download_status": download_status,
                "is_downloading": is_downloading,
                "watched_percent": _compute_watched_percent(local_path) if local_path else 0.0,
                "in_library": in_library,
            })
        return items

    def _find_shared_series_raw(self, share_id: str) -> dict | None:
        needle = (share_id or "").strip()
        if not needle:
            return None
        from src import share_manager

        for item in share_manager.get_cached_items():
            if str(item.get("id") or "") == needle:
                return item
        for item in self._all_video_shared:
            if str(item.get("share_id") or "") == needle:
                return item
        return None

    def _find_shared_series_model(self, share_id: str) -> dict | None:
        needle = (share_id or "").strip()
        if not needle:
            return None
        for item in self._all_video_shared:
            if str(item.get("share_id") or "") == needle:
                return item
        return None

    def _queue_shared_episode_download(self, series: dict, episode: dict, folder: str) -> None:
        source_url = str(episode.get("source_url") or "").strip()
        if not source_url or self._episode_in_library(episode):
            return
        episode["is_downloading"] = True
        episode["download_status"] = "downloading"
        episode["download_percent"] = float(episode.get("download_percent") or 0.0)
        self._persist_shared_series_state(series)
        self._refresh_shared_series_model(series)
        self.downloadMedia(source_url, "video", folder)

    def _persist_shared_series_state(self, series: dict) -> None:
        from src import share_manager

        share_id = str(series.get("share_id") or series.get("id") or "").strip()
        if not share_id:
            return
        episodes = list(series.get("episodes") or [])
        items = share_manager.get_cached_items()
        changed = False
        for item in items:
            if str(item.get("id") or "") != share_id:
                continue
            item["episodes"] = episodes
            changed = True
            break
        if changed:
            from src.share_manager import _read_local_file, _write_local_file
            from src.device_store import get_device_id
            import time

            data = _read_local_file()
            _write_local_file({
                "device_id": data.get("device_id") or get_device_id(),
                "fetched_at": time.time(),
                "items": items,
            })

    def _refresh_shared_series_model(self, series: dict) -> None:
        share_id = str(series.get("share_id") or series.get("id") or "")
        raw = self._find_shared_series_raw(share_id)
        source = raw or series
        for index, item in enumerate(self._all_video_shared):
            if str(item.get("share_id") or "") != share_id:
                continue
            updated = self._shared_item_to_model(
                {**source, **item, "episodes": list(source.get("episodes") or [])},
                index,
            )
            self._all_video_shared[index] = updated
            if self._current_page == 3 and not self.inCollectionView and self._shared_series_index < 0:
                self._apply_library_filter(self._all_video_shared, self._video_shared_model)
            if self._shared_series_index >= 0:
                model_item = self._video_shared_model.item_at(self._shared_series_index)
                if model_item is not None and str(model_item.get("share_id") or "") == share_id:
                    self._video_model.set_items(self._shared_series_episode_items(updated))
            self.libraryNavigationChanged.emit()
            break

    def _find_shared_item(self, key: str) -> dict | None:
        needle = (key or "").strip()
        if not needle:
            return None
        for item in self._all_video_shared:
            if item.get("is_series"):
                for episode in item.get("episodes") or []:
                    source_url = str(episode.get("source_url") or "").strip()
                    track_id = extract_youtube_id(source_url) or source_url
                    if track_id == needle or source_url == needle:
                        return item
                continue
            if item.get("track_id") == needle or item.get("url") == needle:
                return item
        for item in self._all_music_shared:
            if item.get("is_playlist"):
                for track in item.get("episodes") or []:
                    source_url = str(track.get("source_url") or "").strip()
                    track_id = extract_youtube_id(source_url) or source_url
                    if track_id == needle or source_url == needle:
                        return item
                continue
            if item.get("track_id") == needle or item.get("url") == needle:
                return item
        return None

    def _find_shared_episode(self, key: str) -> tuple[dict, dict] | None:
        needle = (key or "").strip()
        if not needle:
            return None
        for item in self._all_video_shared:
            if not item.get("is_series"):
                continue
            for episode in item.get("episodes") or []:
                source_url = str(episode.get("source_url") or "").strip()
                track_id = extract_youtube_id(source_url) or source_url
                if track_id == needle or source_url == needle:
                    return item, episode
        return None

    def _find_shared_playlist_track(self, key: str) -> tuple[dict, dict] | None:
        needle = (key or "").strip()
        if not needle:
            return None
        for item in self._all_music_shared:
            if not item.get("is_playlist"):
                continue
            for track in item.get("episodes") or []:
                source_url = str(track.get("source_url") or "").strip()
                track_id = extract_youtube_id(source_url) or source_url
                if track_id == needle or source_url == needle:
                    return item, track
        return None

    def _mark_shared_downloading(self, item: dict, *, percent: float) -> None:
        item["is_downloading"] = True
        item["download_status"] = "downloading"
        item["download_percent"] = percent
        self._emit_shared_item_changed(item, pool="video")

    def _mark_music_shared_downloading(self, item: dict, *, percent: float) -> None:
        item["is_downloading"] = True
        item["download_status"] = "downloading"
        item["download_percent"] = percent
        self._emit_shared_item_changed(item, pool="music")

    def _emit_shared_item_changed(self, item: dict, *, pool: str = "video") -> None:
        track_id = str(item.get("track_id") or "")
        url = str(item.get("url") or "")
        model = self._music_shared_model if pool == "music" else self._video_shared_model
        model.update_download_state(
            track_id,
            percent=item.get("download_percent"),
            status=item.get("download_status"),
            is_downloading=item.get("is_downloading"),
        )
        if url and url != track_id:
            model.update_download_state(
                url,
                percent=item.get("download_percent"),
                status=item.get("download_status"),
                is_downloading=item.get("is_downloading"),
            )

    def _on_shared_download_started(self, key: str) -> None:
        match = self._find_shared_episode(key)
        if match is not None:
            series, episode = match
            episode["is_downloading"] = True
            episode["download_status"] = "downloading"
            self._persist_shared_series_state(series)
            self._refresh_shared_series_model(series)
            return
        playlist_match = self._find_shared_playlist_track(key)
        if playlist_match is not None:
            playlist, track = playlist_match
            track["is_downloading"] = True
            track["download_status"] = "downloading"
            self._persist_shared_playlist_state(playlist)
            self._refresh_shared_playlist_model(playlist)
            return
        item = self._find_shared_item(key)
        if item is None or item.get("is_series") or item.get("is_playlist"):
            return
        if item.get("audio_only"):
            self._mark_music_shared_downloading(item, percent=float(item.get("download_percent") or 0.0))
        else:
            self._mark_shared_downloading(item, percent=float(item.get("download_percent") or 0.0))

    def _on_shared_download_progress(self, key: str, percent: float) -> None:
        match = self._find_shared_episode(key)
        if match is not None:
            series, episode = match
            self._patch_shared_episode_progress(series, episode, percent)
            return
        playlist_match = self._find_shared_playlist_track(key)
        if playlist_match is not None:
            playlist, track = playlist_match
            self._patch_shared_track_progress(playlist, track, percent)
            return
        item = self._find_shared_item(key)
        if item is None or item.get("is_series") or item.get("is_playlist"):
            return
        item["download_percent"] = percent
        item["download_status"] = "downloading"
        item["is_downloading"] = True
        pool = "music" if item.get("audio_only") else "video"
        self._emit_shared_item_changed(item, pool=pool)

    def _find_shared_playlist_model(self, share_id: str) -> dict | None:
        needle = (share_id or "").strip()
        if not needle:
            return None
        for item in self._all_music_shared:
            if str(item.get("share_id") or "") == needle:
                return item
        return None

    def _schedule_shared_progress_persist(self, share_id: str, *, pool: str) -> None:
        needle = (share_id or "").strip()
        if not needle:
            return
        if pool == "music":
            self._shared_playlist_pending_persist.add(needle)
        else:
            self._shared_series_pending_persist.add(needle)
        if not self._shared_progress_save_timer.isActive():
            self._shared_progress_save_timer.start()

    def _flush_shared_progress_state(self) -> None:
        for share_id in list(self._shared_series_pending_persist):
            series = self._find_shared_series_model(share_id)
            if series:
                self._persist_shared_series_state(series)
        self._shared_series_pending_persist.clear()
        for share_id in list(self._shared_playlist_pending_persist):
            playlist = self._find_shared_playlist_model(share_id)
            if playlist:
                self._persist_shared_playlist_state(playlist)
        self._shared_playlist_pending_persist.clear()

    def _patch_shared_episode_progress(
        self,
        series: dict,
        episode: dict,
        percent: float,
    ) -> None:
        episode["download_percent"] = percent
        episode["download_status"] = "downloading"
        episode["is_downloading"] = True
        share_id = str(series.get("share_id") or series.get("id") or "")
        self._schedule_shared_progress_persist(share_id, pool="video")
        source_url = str(episode.get("source_url") or "").strip()
        track_id = extract_youtube_id(source_url) or source_url
        if self._shared_series_index >= 0:
            model_item = self._video_shared_model.item_at(self._shared_series_index)
            if model_item is not None and str(model_item.get("share_id") or "") == share_id:
                self._video_model.update_download_state(
                    track_id,
                    percent=percent,
                    status="downloading",
                    is_downloading=True,
                )

    def _patch_shared_track_progress(
        self,
        playlist: dict,
        track: dict,
        percent: float,
    ) -> None:
        track["download_percent"] = percent
        track["download_status"] = "downloading"
        track["is_downloading"] = True
        share_id = str(playlist.get("share_id") or playlist.get("id") or "")
        self._schedule_shared_progress_persist(share_id, pool="music")
        source_url = str(track.get("source_url") or "").strip()
        track_id = extract_youtube_id(source_url) or source_url
        if self._shared_playlist_index >= 0:
            model_item = self._music_shared_model.item_at(self._shared_playlist_index)
            if model_item is not None and str(model_item.get("share_id") or "") == share_id:
                self._music_model.update_download_state(
                    track_id,
                    percent=percent,
                    status="downloading",
                    is_downloading=True,
                )

    def _on_shared_download_finished(self, video_id: str, file_path: str) -> None:
        self._flush_shared_progress_state()
        match = self._find_shared_episode(video_id)
        if match is not None:
            series, episode = match
            episode["is_downloading"] = False
            episode["download_status"] = "done"
            episode["download_percent"] = 100.0
            if file_path:
                set_metadata(
                    file_path,
                    source_id=video_id,
                    source_url=str(episode.get("source_url") or "").strip(),
                )
            self._persist_shared_series_state(series)
            self._refresh_shared_series_model(series)
            if self._shared_series_in_library(series):
                share_id = str(series.get("share_id") or "").strip()
                self._remove_shared_item_by_id(share_id)
                if share_id:
                    asyncio.create_task(self._dismiss_shared_after_download(share_id))
            return

        playlist_match = self._find_shared_playlist_track(video_id)
        if playlist_match is not None:
            playlist, track = playlist_match
            track["is_downloading"] = False
            track["download_status"] = "done"
            track["download_percent"] = 100.0
            if file_path:
                set_metadata(
                    file_path,
                    source_id=video_id,
                    source_url=str(track.get("source_url") or "").strip(),
                )
            self._persist_shared_playlist_state(playlist)
            self._refresh_shared_playlist_model(playlist)
            if self._shared_playlist_in_library(playlist):
                share_id = str(playlist.get("share_id") or "").strip()
                self._remove_shared_item_by_id(share_id)
                if share_id:
                    asyncio.create_task(self._dismiss_shared_after_download(share_id))
            return

        item = self._find_shared_item(video_id)
        if item is None or item.get("is_series") or item.get("is_playlist"):
            return
        share_id = str(item.get("share_id") or "").strip()
        self._remove_shared_item_by_id(share_id)
        if share_id:
            asyncio.create_task(self._dismiss_shared_after_download(share_id))
        if file_path:
            set_metadata(
                file_path,
                source_id=video_id,
                source_url=str(item.get("url") or "").strip(),
            )

    def _on_shared_download_error(self, key: str, _message: str) -> None:
        self._flush_shared_progress_state()
        match = self._find_shared_episode(key)
        if match is not None:
            series, episode = match
            episode["is_downloading"] = False
            episode["download_status"] = "pending"
            self._persist_shared_series_state(series)
            self._refresh_shared_series_model(series)
            return
        playlist_match = self._find_shared_playlist_track(key)
        if playlist_match is not None:
            playlist, track = playlist_match
            track["is_downloading"] = False
            track["download_status"] = "pending"
            self._persist_shared_playlist_state(playlist)
            self._refresh_shared_playlist_model(playlist)
            return
        item = self._find_shared_item(key)
        if item is None or item.get("is_series") or item.get("is_playlist"):
            return
        item["is_downloading"] = False
        item["download_status"] = "pending"
        pool = "music" if item.get("audio_only") else "video"
        self._emit_shared_item_changed(item, pool=pool)

    @pyqtSlot()
    def playCollection(self) -> None:
        if self.inSharedSeriesView:
            series = self._video_shared_model.item_at(self._shared_series_index)
            if series is None:
                return
            episodes = self._shared_series_episode_items(series)
            playable = [
                ep for ep in episodes
                if ep.get("download_status") == "done" or self._episode_in_library(ep)
            ]
            if not playable:
                return
            resume = self._resume_item_in_collection(playable)
            self._set_playback_queue(playable)
            self._play_item(resume or playable[0])
            return
        if self.inSharedPlaylistView:
            playlist = self._music_shared_model.item_at(self._shared_playlist_index)
            if playlist is None:
                return
            tracks = self._shared_playlist_track_items(playlist)
            playable = [
                track for track in tracks
                if track.get("download_status") == "done" or self._shared_track_in_library(track)
            ]
            if not playable:
                return
            resume = self._resume_item_in_collection(playable)
            self._set_playback_queue(playable)
            self._play_item(resume or playable[0])
            return
        items = self._collection_media_items()
        if not items:
            return
        resume = self._resume_item_in_collection(items)
        self._set_playback_queue(items)
        self._play_item(resume or items[0])

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
        if self._current_page not in {2, 3}:
            return
        model = self._model_for_page(self._current_page)
        item = model.item_at(index)
        if item is None or not item.get("is_collection"):
            return
        if self._current_page == 2:
            self._music_section = "albums"
        elif self._current_page == 3:
            self._video_section = "series"
        self._folder_stack_for_page(self._current_page).append(
            self._make_folder_stack_entry(Path(item["path"]))
        )
        self._reload_library_view(self._current_page)

    @pyqtSlot()
    def goBackLibrary(self) -> None:
        if self._shared_series_index >= 0:
            self.goBackSharedSeries()
            return
        if self._shared_playlist_index >= 0:
            self.goBackSharedPlaylist()
            return
        if self._movie_detail_index >= 0 or self._shared_movie_detail_index >= 0:
            self._movie_detail_index = -1
            self._shared_movie_detail_index = -1
            self.libraryNavigationChanged.emit()
            return
        stack = self._folder_stack_for_page(self._current_page)
        if not stack:
            return
        stack.pop()
        self._reload_library_view(self._current_page)

    @pyqtSlot()
    def goBack(self) -> None:
        if self._current_page == 3 and self.inSharedSeriesView:
            self.goBackSharedSeries()
        elif self._current_page == 2 and self.inSharedPlaylistView:
            self.goBackSharedPlaylist()
        elif self._current_page == 3 and self.inMovieDetailView:
            self.goBackLibrary()
        elif self._current_page in {2, 3} and self._folder_stack_for_page(self._current_page):
            self.goBackLibrary()
        elif self._current_page != 2:
            self.setCurrentPage(2)

    @pyqtSlot(str)
    def createFolder(self, name: str) -> None:
        if self._current_page not in {2, 3}:
            return
        parent = self._current_library_folder()
        if self._current_page == 3 and not self.inCollectionView:
            default_name = "Phim bộ mới"
        elif self._current_page == 3:
            default_name = "Thư mục mới"
        else:
            default_name = "Playlist mới"
        base = (name or default_name).strip() or default_name
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
        if self._current_page not in {2, 3}:
            return
        src = Path(source_path)
        dest_dir = Path(dest_folder_path)
        if not src.exists() or not dest_dir.is_dir():
            return
        if src.resolve() == dest_dir.resolve() or dest_dir.resolve().is_relative_to(src.resolve()):
            return
        if src.suffix.lower() in AUDIO_EXTS and self._current_page == 2:
            if add_track_to_album(src, dest_dir) is None:
                return
            self._load_music_library(refresh=True)
            return
        target = dest_dir / src.name
        if target.exists():
            return
        try:
            shutil.move(str(src), str(target))
        except OSError as exc:
            logger.error("Failed to move %s -> %s: %s", src, target, exc)
            return
        migrate_metadata(str(src.resolve()), str(target.resolve()))
        self._reload_current_library(refresh=True)

    @pyqtSlot(int)
    def moveMediaOutOfFolder(self, index: int) -> None:
        if self._current_page not in {2, 3}:
            return
        stack = self._folder_stack_for_page(self._current_page)
        if not stack:
            return
        model = self._collection_list_model() if self.inCollectionView else self._model_for_page(self._current_page)
        item = model.item_at(index)
        if item is None or item.get("is_collection"):
            return
        src = Path(item["path"])
        if self._is_all_musics_virtual(stack[-1].path):
            try:
                album_dir = src.parent.resolve()
            except OSError:
                return
            music_root = Path(self._music_dir).resolve()
            if album_dir == music_root:
                return
        else:
            album_dir = stack[-1].path
        if src.suffix.lower() in AUDIO_EXTS and self._current_page == 2:
            if not remove_track_from_album(src, album_dir, Path(self._music_dir)):
                return
            self._reload_library_view(self._current_page)
            return
        dest_dir = album_dir.parent
        target = dest_dir / src.name
        if target.exists():
            return
        try:
            shutil.move(str(src), str(target))
        except OSError as exc:
            logger.error("Failed to move %s out of folder: %s", src, exc)
            return
        migrate_metadata(str(src.resolve()), str(target.resolve()))
        self._reload_library_view(self._current_page)

    @pyqtSlot(str, result=bool)
    def mediaCanMoveToSeries(self, source_path: str) -> bool:
        """True when a video file is loose at the Videos root (not inside a series folder)."""
        return video_can_move_to_series(source_path, self._video_dir)

    @pyqtSlot(str, result=bool)
    def mediaCanMoveToPlaylist(self, source_path: str) -> bool:
        """True when an audio file is loose at the Music root (not inside a playlist)."""
        return audio_can_move_to_playlist(source_path, self._music_dir)

    @pyqtSlot(str, result=list)
    def foldersForMove(self, source_path: str) -> list[dict]:
        """Playlists in the library available as add targets for *source_path*."""
        if self._current_page not in {2, 3}:
            return []
        exclude: Path | None = None
        source_parent: Path | None = None
        media_canonical: Path | None = None
        if source_path:
            try:
                src = Path(source_path)
                exclude = src.resolve() if src.is_dir() else None
                if src.is_file():
                    source_parent = src.parent.resolve()
                    if src.suffix.lower() in AUDIO_EXTS | VIDEO_EXTS:
                        media_canonical = canonical_path(src)
            except OSError:
                exclude = None
        folder = self._current_library_folder()
        if media_canonical is not None and self._current_page in {2, 3}:
            folder = self._root_dir_for_page(self._current_page)
        if not folder.is_dir():
            return []
        targets: list[dict] = []
        for child in sorted(folder.iterdir()):
            if not child.is_dir() or child.name.startswith("."):
                continue
            try:
                resolved = child.resolve()
            except OSError:
                continue
            if exclude is not None and resolved == exclude:
                continue
            if source_parent is not None and resolved == source_parent:
                continue
            if media_canonical is not None and playlist_contains_media(child, media_canonical):
                continue
            targets.append({"title": child.name, "path": str(resolved)})
        return targets

    @pyqtSlot(str, str)
    def moveMediaToFolder(self, source_path: str, dest_folder_path: str) -> None:
        self.moveMediaByPath(source_path, dest_folder_path)

    @pyqtSlot(int)
    def moveCollectionItemUp(self, index: int) -> None:
        if index <= 0:
            return
        self.reorderCollectionItems(index, index - 1)

    @pyqtSlot(int)
    def moveCollectionItemDown(self, index: int) -> None:
        model = self._collection_list_model()
        if index < 0 or index >= model.rowCount() - 1:
            return
        self.reorderCollectionItems(index, index + 1)

    @pyqtSlot(int, int)
    def reorderCollectionItems(self, from_index: int, to_index: int) -> None:
        if self._current_page not in {2, 3}:
            return
        if from_index == to_index:
            return
        stack = self._folder_stack_for_page(self._current_page)
        if stack and self._is_all_musics_virtual(stack[-1].path):
            return
        model = self._collection_list_model() if self.inCollectionView else self._model_for_page(self._current_page)
        paths = model.item_paths()
        if not (0 <= from_index < len(paths) and 0 <= to_index < len(paths)):
            return
        moved = paths.pop(from_index)
        paths.insert(to_index, moved)
        names = [Path(p).name for p in paths]
        self._clear_playlist_order_undo()
        self._apply_collection_order(names)

    @pyqtSlot()
    def shuffleCollectionOrder(self) -> None:
        if not self._can_shuffle_collection_order():
            return
        folder_key = str(self._current_library_folder())
        model = self._collection_list_model()
        names = [Path(p).name for p in model.item_paths()]
        self._playlist_order_undo[folder_key] = list(names)
        shuffled = list(names)
        random.shuffle(shuffled)
        if len(shuffled) > 1:
            for _ in range(10):
                if shuffled != names:
                    break
                random.shuffle(shuffled)
        self._apply_collection_order(shuffled)
        self.playlistOrderUndoChanged.emit()

    @pyqtSlot()
    def undoCollectionOrderShuffle(self) -> None:
        folder_key = self._playlist_order_folder_key()
        if folder_key is None:
            return
        saved = self._playlist_order_undo.pop(folder_key, None)
        if saved is None:
            return
        self._apply_collection_order(saved)
        self.playlistOrderUndoChanged.emit()

    @pyqtSlot()
    def quitApp(self) -> None:
        import os
        try:
            self.cleanup()
        except Exception as e:
            logger.error("Error during quit cleanup: %s", e)
        app = QApplication.instance()
        if app is not None:
            app.quit()
        os._exit(0)

    @pyqtSlot(str)
    def deleteMediaByPath(self, path: str) -> None:
        value = path.strip()
        if not value or self._is_all_musics_virtual(value):
            return
        target = Path(value)
        try:
            video_root = Path(self._video_dir).resolve()
            music_root = Path(self._music_dir).resolve()
            resolved = target.resolve()
            in_video = resolved == video_root or video_root in resolved.parents
            in_music = resolved == music_root or music_root in resolved.parents
        except OSError:
            in_video = in_music = False

        try:
            if target.is_dir():
                shutil.rmtree(target)
            elif target.is_file():
                target.unlink()
            else:
                return
        except OSError as exc:
            logger.error("Failed to delete %s: %s", target, exc)
            return
        delete_metadata(str(target))

        if self._current_path and (
            self._path_matches_item(self._current_path, {"path": value})
            or self._current_path_under(target)
        ):
            self._clear_current_track()

        if in_video:
            self._load_video_library(refresh=True)
        elif in_music:
            self._load_music_library(refresh=True)
        else:
            self._reload_current_library(refresh=True)

    @pyqtSlot(int)
    def deleteMediaAt(self, index: int) -> None:
        model = self._collection_list_model() if self.inCollectionView else self._model_for_page(self._current_page)
        item = model.item_at(index)
        if item is None:
            return
        self.deleteMediaByPath(item.get("path", ""))

    @pyqtSlot(str, str, str)
    def editMediaMetadataByPath(self, path: str, title: str, artist: str) -> None:
        value = _resolve_metadata_path(path)
        if not value or self._is_all_musics_virtual(value):
            return
        set_metadata(
            value,
            title=title.strip(),
            artist=artist.strip(),
        )
        self._reload_current_library(refresh=True)

    @pyqtSlot(int, str, str)
    def editMediaMetadata(self, index: int, title: str, artist: str) -> None:
        model = self._collection_list_model() if self.inCollectionView else self._model_for_page(self._current_page)
        item = model.item_at(index)
        if item is None:
            return
        self.editMediaMetadataByPath(_metadata_path(item), title, artist)

    @pyqtSlot(str)
    def pickMediaCoverByPath(self, path: str) -> None:
        value = _resolve_metadata_path(path)
        if not value or self._is_all_musics_virtual(value):
            return
        QTimer.singleShot(0, lambda p=value: self._apply_picked_cover_path(p))

    def _apply_picked_cover_path(self, path: str) -> None:
        item_path = path.strip()
        start = ""
        if item_path:
            resolved = Path(item_path)
            start = str(resolved.parent if resolved.is_file() else resolved)
        chosen = self._pick_image_file("Chọn ảnh bìa", start)
        if not chosen:
            return
        set_cover_image(item_path, chosen)
        self._reload_current_library(refresh=True)

    @pyqtSlot(int)
    def pickMediaCover(self, index: int) -> None:
        model = self._collection_list_model() if self.inCollectionView else self._model_for_page(self._current_page)
        item = model.item_at(index)
        if item is None:
            return
        self.pickMediaCoverByPath(_metadata_path(item))

    def set_main_window(self, window: QWindow | None) -> None:
        self._main_window = window

    def show_main_window(self) -> None:
        if self._main_window is None:
            return
        self._main_window.setVisible(True)
        self._main_window.raise_()
        self._main_window.requestActivate()
        # GridView delegates may not load thumbnails while the splash was covering
        # the window; refresh once the main UI is actually visible.
        QTimer.singleShot(0, self._refresh_visible_library_views)

    def _pick_image_file(self, title: str, start_dir: str = "") -> str:
        initial = start_dir or str(Path.home())
        if not Path(initial).exists():
            initial = str(Path.home())
        chosen, _ = QFileDialog.getOpenFileName(
            None,
            title,
            initial,
            "Image files (*.png *.jpg *.jpeg *.webp *.bmp);;All files (*)",
        )
        return chosen or ""

    def _pick_directory(self, title: str, start_dir: str = "") -> str:
        initial = start_dir or str(Path.home())
        if not Path(initial).exists():
            initial = str(Path.home())
        chosen = QFileDialog.getExistingDirectory(None, title, initial)
        return chosen or ""

    @pyqtSlot(str)
    def copyToClipboard(self, text: str) -> None:
        value = text.strip()
        if value:
            QGuiApplication.clipboard().setText(value)

    @pyqtSlot()
    def refreshLibraries(self) -> None:
        if self._music_library_loaded:
            self._load_music_library(refresh=True)
            if self._current_page == 2:
                self._sync_library_page_view(2)
        if self._video_library_loaded or self._pending_video_downloads > 0:
            self._load_video_library(refresh=True)
            if self._current_page == 3:
                self._sync_library_page_view(3)

    @pyqtSlot()
    def rescanLibrary(self) -> None:
        """Rescan libraries that were already loaded this session."""
        self.refreshLibraries()

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
            self.searchResults.emit(self._annotate_search_results(list(results or []), media_type))

    @pyqtSlot(str, str)
    def resolveLink(self, url: str, media_type: str) -> None:
        """Expand a pasted URL (single video or playlist) for link-mode intake."""
        self._search_seq += 1
        asyncio.create_task(self._resolve_link(url, media_type, self._search_seq))

    async def _resolve_link(self, url: str, media_type: str, seq: int) -> None:
        value = url.strip()
        if not value:
            if seq == self._search_seq:
                self.searchError.emit("URL hoặc video ID không hợp lệ.")
            return
        try:
            resolved = await asyncio.wait_for(
                self.downloader.resolve_link(value, media_type),
                timeout=30,
            )
        except TimeoutError:
            if seq == self._search_seq:
                self.searchError.emit("Đọc link quá thời gian chờ (30 giây). Vui lòng thử lại.")
            return
        except DownloadFailed as exc:
            logger.exception("Link resolve failed for %r", value)
            if seq == self._search_seq:
                self.searchError.emit(str(exc))
            return
        if seq != self._search_seq:
            return
        items = self._annotate_search_results(list(resolved.get("items") or []), media_type)
        folder = str(resolved.get("playlist_folder") or "").strip()
        if folder:
            self.playlistLinkReady.emit(folder, items)
        else:
            self.searchResults.emit(items)

    @pyqtSlot(str, list, result=list)
    def annotateDownloadResults(self, media_type: str, items: list) -> list:
        """Re-check library membership for visible download rows."""
        normalized: list[dict] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            normalized.append({
                "id": str(item.get("id") or ""),
                "url": str(item.get("url") or ""),
                "title": str(item.get("title") or ""),
                "artist": str(item.get("artist") or ""),
                "duration": str(item.get("duration") or ""),
                "thumbnail_url": str(
                    item.get("thumbnail_url") or item.get("thumbnail") or ""
                ),
            })
        return self._annotate_search_results(normalized, media_type)

    @pyqtSlot(str)
    def readLinksFromFile(self, media_type: str) -> None:
        """Open a file dialog for .txt, read links, queue them for download."""
        parent = QApplication.activeWindow()
        path, _ = QFileDialog.getOpenFileName(
            parent, "Chọn file danh sách link", "",
            "Text files (*.txt);;All files (*)",
        )
        if not path:
            return
        try:
            text = Path(path).read_text(encoding="utf-8")
        except Exception as exc:
            self.searchError.emit(f"Không thể đọc file: {exc}")
            return
        # Extract one URL per line (ignore comments and blanks)
        urls = []
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("//"):
                continue
            urls.append(line)
        if not urls:
            self.searchError.emit("Không tìm thấy link nào trong file.")
            return
        # Queue all links for download
        for url in urls:
            self.downloadMedia(url, media_type, "")
        self.searchResults.emit([
            {"title": f"Đã thêm {len(urls)} link vào hàng đợi",
             "artist": f"Từ file: {Path(path).name}",
             "url": "", "id": "", "duration": "",
             "in_library": False}
        ])

    @pyqtSlot(str, str, str)
    def downloadMedia(self, url: str, kind: str, output_subdir: str = "") -> None:
        """Enqueue an audio/video download; jobs run one at a time."""
        value = url.strip()
        if not value:
            self.downloadError.emit("", "URL hoặc video ID không hợp lệ.")
            return
        media_type = "music" if kind in {"audio", "music"} else kind
        if media_type not in {"music", "video"}:
            self.downloadError.emit(value, "Loại media không được hỗ trợ.")
            return
        subdir = output_subdir.strip()
        self._enqueue_download(_DownloadJob(value, media_type, subdir, self._download_quality))

    @pyqtSlot(str, str, result=bool)
    def removeQueuedDownload(self, url: str, media_kind: str) -> bool:
        """Remove a job that is still waiting in the download queue.

        A job already reported as ``downloadJobStarted`` is intentionally not
        cancelled here: yt-dlp/ffmpeg does not currently expose a safe
        cancellation handle, and removing only its row would leave the
        backend counters inconsistent.  The UI hides the remove button for
        that state.
        """
        value = str(url or "").strip()
        kind = "music" if str(media_kind or "").strip() in {"music", "audio"} else "video"
        if not value:
            return False

        removed: list[_DownloadJob] = []
        queue = self._download_queue
        if queue is not None:
            queued_jobs = list(queue._queue)
            kept_jobs = [
                job
                for job in queued_jobs
                if not (job.url == value and job.media_type == kind)
            ]
            removed.extend(
                job for job in queued_jobs
                if job.url == value and job.media_type == kind
            )
            if removed:
                queue._queue.clear()
                queue._queue.extend(kept_jobs)

        deferred = [
            job for job in self._deferred_403_jobs
            if job.url == value and job.media_type == kind
        ]
        if deferred:
            removed.extend(deferred)
            self._deferred_403_jobs = [
                job for job in self._deferred_403_jobs
                if not (job.url == value and job.media_type == kind)
            ]

        if not removed:
            return False

        for job in removed:
            if job.media_type != "music":
                self._pending_video_downloads = max(0, self._pending_video_downloads - 1)
            self._untrack_download_subdir(job.media_type, job.output_subdir)
        self._refresh_download_concurrency()
        return True

    @pyqtSlot(str, str)
    def queueLink(self, url: str, media_type: str) -> None:
        """Resolve a link asynchronously and enqueue all items (video or playlist)."""
        asyncio.create_task(self._queue_link(url, media_type))

    async def _queue_link(self, url: str, media_type: str) -> None:
        value = url.strip()
        if not value:
            self.linkQueueError.emit(value, "URL hoặc video ID không hợp lệ.")
            return
        try:
            resolved = await asyncio.wait_for(
                self.downloader.resolve_link(value, media_type),
                timeout=30,
            )
        except TimeoutError:
            self.linkQueueError.emit(value, "Đọc link quá thời gian chờ (30 giây).")
            return
        except DownloadFailed as exc:
            logger.exception("Link queue resolve failed for %r", value)
            self.linkQueueError.emit(value, str(exc))
            return
        items = self._annotate_search_results(list(resolved.get("items") or []), media_type)
        folder = str(resolved.get("playlist_folder") or "").strip()
        downloadable = [item for item in items if not item.get("in_library")]
        if not downloadable:
            self.linkQueueError.emit(value, "Tất cả mục trong link đã có trong thư viện.")
            return
        kind = "music" if media_type == "music" else "video"
        for item in downloadable:
            item_url = str(item.get("url") or item.get("id") or "").strip()
            if item_url:
                self._enqueue_download(_DownloadJob(item_url, kind, folder, self._download_quality))
        self.playlistQueued.emit(folder, media_type, downloadable)

    def _ensure_download_worker(self) -> asyncio.Queue[_DownloadJob]:
        if self._download_queue is None:
            self._download_queue = asyncio.Queue()
        if not self._download_worker_started:
            self._download_worker_started = True
            asyncio.create_task(self._download_worker())
        return self._download_queue

    def _enqueue_download(self, job: _DownloadJob) -> None:
        queue = self._ensure_download_worker()
        queue.put_nowait(job)
        if job.media_type != "music":
            self._pending_video_downloads += 1
        self._track_download_subdir(job.media_type, job.output_subdir)
        self._start_library_hotload_timer()
        self._refresh_download_concurrency()

    def _download_backlog_size(self) -> int:
        queue = self._download_queue
        pending = queue.qsize() if queue else 0
        return pending + self._download_jobs_in_progress

    def _network_is_good(self) -> bool:
        return self._download_speed_ema >= _GOOD_NETWORK_BPS

    def _download_concurrency_limit(self) -> int:
        if self._download_backlog_size() <= _LARGE_BATCH_THRESHOLD:
            return 1
        if not self._network_is_good():
            return 1
        return _MAX_CONCURRENT_DOWNLOADS

    def _refresh_download_concurrency(self) -> None:
        limit = self._download_concurrency_limit()
        if limit != self._published_download_concurrency:
            self._published_download_concurrency = limit
            self.downloadConcurrencyChanged.emit()

    def _record_download_speed(self, speed_bps: float) -> None:
        if speed_bps <= 0:
            return
        if self._download_speed_ema <= 0:
            self._download_speed_ema = speed_bps
        else:
            self._download_speed_ema = 0.8 * self._download_speed_ema + 0.2 * speed_bps
        self._refresh_download_concurrency()

    async def _run_download_job(self, job: _DownloadJob) -> None:
        self._download_jobs_in_progress += 1
        self._refresh_download_concurrency()
        self._start_library_hotload_timer()
        finished = False
        try:
            self.downloadJobStarted.emit(job.url)
            try:
                video_id, file_path = await self._execute_download(
                    job.url,
                    job.media_type,
                    job.output_subdir,
                    job.quality,
                )
            except Download403Failed as exc:
                if job.retry_403:
                    logger.exception("Media download failed on 403 retry for %r", job.url)
                    self.downloadError.emit(job.url, str(exc))
                    finished = True
                else:
                    logger.warning("HTTP 403 for %r, deferring until batch end", job.url)
                    self._deferred_403_jobs.append(job)
                    self.downloadJobRequeued.emit(job.url)
                return
            except DownloadFailed as exc:
                logger.exception("Media download failed for %r", job.url)
                self.downloadError.emit(job.url, str(exc))
                finished = True
                return

            finished = True
            self.downloadFinished.emit(video_id, file_path)
            resolved_path = str(Path(file_path).resolve())
            set_metadata(
                resolved_path,
                source_id=video_id,
                source_url=canonical_source_url(job.url, video_id=video_id),
                subtitle_path=(
                    find_video_subtitle_paths(Path(resolved_path)) or [None]
                )[0],
            )
            if job.media_type == "music":
                self._music_source_ids.add(video_id)
            else:
                self._video_source_ids.add(video_id)
            self._hotload_after_download(job, file_path)
        finally:
            self._download_jobs_in_progress -= 1
            if finished and job.media_type != "music":
                self._pending_video_downloads = max(0, self._pending_video_downloads - 1)
            if finished:
                self._untrack_download_subdir(job.media_type, job.output_subdir)
            self._refresh_download_concurrency()

    async def _download_worker(self) -> None:
        queue = self._ensure_download_worker()
        in_flight: set[asyncio.Task[None]] = set()

        async def reap_one() -> None:
            if not in_flight:
                return
            done, _ = await asyncio.wait(in_flight, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                in_flight.discard(task)
                try:
                    await task
                except Exception:
                    logger.exception("Download task failed unexpectedly")

        async def wait_for_slot() -> None:
            while len(in_flight) >= self._download_concurrency_limit():
                await reap_one()

        while True:
            await wait_for_slot()

            if queue.empty():
                if in_flight:
                    await reap_one()
                    continue
                if self._deferred_403_jobs:
                    pending = self._deferred_403_jobs
                    self._deferred_403_jobs = []
                    for deferred in pending:
                        queue.put_nowait(replace(deferred, retry_403=True))
                    self._refresh_download_concurrency()
                    continue
                self._download_speed_ema = 0.0
                self._refresh_download_concurrency()
                self._stop_library_hotload_timer()
                self.rescanLibrary()
                job = await queue.get()
            else:
                job = await queue.get()

            task = asyncio.create_task(self._run_download_job(job))
            in_flight.add(task)

            def _on_task_done(t: asyncio.Task[None]) -> None:
                in_flight.discard(t)
                queue.task_done()

            task.add_done_callback(_on_task_done)

    async def _execute_download(
        self,
        url: str,
        media_type: str,
        output_subdir: str = "",
        quality: str = "1080",
    ) -> tuple[str, str]:
        active_id = url

        def hook(data: dict) -> None:
            nonlocal active_id
            info = data.get("info_dict") or {}
            active_id = str(info.get("id") or active_id)
            if data.get("status") != "downloading":
                return
            downloaded = float(data.get("downloaded_bytes") or 0)
            total = float(data.get("total_bytes") or data.get("total_bytes_estimate") or 0)
            percent = min(100.0, downloaded / total * 100.0) if total else 0.0
            self.downloadProgress.emit(active_id, percent)
            speed = float(data.get("speed") or 0)
            if speed > 0:
                self._record_download_speed(speed)

        if media_type not in {"music", "video"}:
            raise DownloadFailed("Loại media không được hỗ trợ.")
        return await self.downloader.download(
            url,
            media_type,
            hook,
            output_subdir=output_subdir or None,
            quality=quality,
        )

    @pyqtSlot()
    def openUiConfigDir(self) -> None:
        open_config_dir()

    @pyqtSlot()
    def reload_app_settings_from_disk(self) -> None:
        """Apply app-level keys from settings.json after an external edit."""
        document = read_settings_document_or_none()
        if document is None:
            return

        raw = load_raw_settings()
        self._ui_config = load_ui_config()

        volume = max(0, min(100, int(raw.get("volume", 100))))
        if volume != self._volume:
            self._volume = volume
            self.volumeChanged.emit()
            self._player.set_volume(volume)

        muted = bool(raw.get("muted", False))
        if muted != self._muted:
            self._muted = muted
            self.mutedChanged.emit()
            self._player.set_muted(muted)

        playback_mode = str(raw.get("video_playback_backend", "inapp")).strip().lower()
        if playback_mode not in {"inapp", "mpv"}:
            playback_mode = "inapp"
        if playback_mode != self._video_playback_mode:
            self._video_playback_mode = playback_mode
            self.videoPlaybackModeChanged.emit()

        quality = _normalize_video_quality(str(raw.get("download_quality", "1080")))
        if quality != self._download_quality:
            self._download_quality = quality
            self.downloadQualityChanged.emit()

        always_visible = bool(
            self._ui_config.get("player_bar", {}).get("always_visible", False)
        )
        if always_visible != self._player_bar_always_visible:
            self._player_bar_always_visible = always_visible
            self._sync_player_bar_for_media(self._current_audio_only)
            self.playerBarVisibleChanged.emit()

        media_root = raw.get("media_root")
        if isinstance(media_root, str) and media_root.strip():
            resolved = str(Path(media_root).expanduser())
            if resolved != self._media_root:
                try:
                    settings = load_settings(create_if_missing=False)
                except OSError:
                    return
                self._apply_storage_settings(settings)
                self._reset_libraries_for_storage_change()

    @pyqtSlot(str)
    def setDownloadQuality(self, quality: str) -> None:
        quality = _normalize_video_quality(quality)
        if self._download_quality != quality:
            self._download_quality = quality
            self.downloadQualityChanged.emit()
            save_raw_settings({"download_quality": quality})

    @pyqtSlot()
    def updateYtDlp(self) -> None:
        if self._yt_dlp_update_status == "Đang cập nhật yt-dlp…":
            return
            
        self._yt_dlp_update_status = "Đang cập nhật yt-dlp…"
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
                     return "yt-dlp đã là phiên bản mới nhất."
                return "Cập nhật yt-dlp thành công."
            except subprocess.CalledProcessError as e:
                return f"Cập nhật thất bại: {e.stderr}"
            except Exception as e:
                return f"Đã xảy ra lỗi: {str(e)}"
                
        def _on_done(future):
            self._yt_dlp_update_status = future.result()
            self.ytDlpUpdateStatusChanged.emit()
            
        task = loop.run_in_executor(None, _run_update)
        asyncio.ensure_future(task).add_done_callback(_on_done)

    def _apply_storage_settings(self, settings: dict[str, str]) -> None:
        self._media_root = settings["media_root"]
        self._music_dir = settings["music_dir"]
        self._video_dir = settings["video_dir"]
        self.downloader.music_dir = Path(self._music_dir)
        self.downloader.video_dir = Path(self._video_dir)
        self.mediaRootChanged.emit()
        self.musicDirChanged.emit()
        self.videoDirChanged.emit()

    @pyqtSlot(result=str)
    def pickMediaRoot(self) -> str:
        chosen = self._pick_directory("Chọn thư mục lưu trữ thư viện", self._media_root)
        if not chosen:
            return ""
        settings = save_settings(chosen)
        self._apply_storage_settings(settings)
        self._settings_saved = True
        self.settingsSavedChanged.emit()
        self._reset_libraries_for_storage_change()
        return chosen

    @pyqtSlot()
    def saveSettings(self) -> None:
        settings = save_settings(self._media_root)
        self._apply_storage_settings(settings)
        self._settings_saved = True
        self.settingsSavedChanged.emit()
        self._reset_libraries_for_storage_change()

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
        self._touch_player_bar()
        if (
            self._player.state.status == PlaybackStatus.STOPPED
            and self._current_path
            and _track_path_available(self._current_path)
        ):
            artist = self._track_artist
            if artist.startswith("•  "):
                artist = artist[3:]
            start_pos = self._last_track_position
            self._last_track_position = 0.0
            self._start_playback(
                self._current_path,
                audio_only=self._current_audio_only,
                title=self._track_title if self._track_title != "LIMINAL" else "",
                artist=artist if artist != "Offline Media Player" else "",
                start_pos=start_pos,
            )
        else:
            self._player.toggle_pause()

    @pyqtSlot()
    def previous(self) -> None:
        self._touch_player_bar()
        if self._current_audio_only and self._current_path:
            self._play_adjacent(-1)
        else:
            self._player.seek(-10)

    @pyqtSlot()
    def next(self) -> None:
        self._touch_player_bar()
        if self._current_audio_only and self._current_path:
            self._play_adjacent(1)
        else:
            self._player.seek(10)

    @pyqtSlot()
    def seekBackward10(self) -> None:
        self._touch_player_bar()
        self._player.seek(-10)

    @pyqtSlot()
    def seekForward10(self) -> None:
        self._touch_player_bar()
        self._player.seek(10)

    def _persist_volume_prefs(self) -> None:
        save_raw_settings({"volume": self._volume, "muted": self._muted})

    @pyqtSlot(str)
    def setVideoPlaybackMode(self, mode: str) -> None:
        mode = str(mode or "inapp").strip().lower()
        if mode not in {"inapp", "mpv"}:
            mode = "inapp"
        if self._video_playback_mode == mode:
            return
        self._video_playback_mode = mode
        self.videoPlaybackModeChanged.emit()
        save_raw_settings({"video_playback_backend": mode})

    @pyqtSlot(float)
    def setVolume(self, vol: float) -> None:
        self._touch_player_bar()
        vol = max(0, min(100, int(round(vol))))
        if vol > 0 and self._muted:
            self._muted = False
            self.mutedChanged.emit()
            self._player.set_mute(False)
        if self._volume != vol:
            self._volume = vol
            self.volumeChanged.emit()
        self._player.set_volume(vol)
        self._volume_save_timer.start()

    @pyqtSlot()
    def toggleMute(self) -> None:
        self._touch_player_bar()
        self._muted = not self._muted
        self.mutedChanged.emit()
        self._player.set_mute(self._muted)
        self._persist_volume_prefs()

    @pyqtSlot()
    def toggleShuffle(self) -> None:
        self._shuffle_on = not self._shuffle_on
        self.shuffleChanged.emit()

    @pyqtSlot()
    def toggleLoop(self) -> None:
        self._loop_mode = (self._loop_mode + 1) % 3
        self.loopModeChanged.emit()

    @pyqtSlot(float)
    def seekTo(self, position: float) -> None:
        self._touch_player_bar()
        self._player.seek_absolute(max(0.0, position))

    # ── Internal ──

    def _model_for_page(self, page: int) -> MediaListModel:
        if page == 2:
            return self._music_albums_model if self._music_section == "albums" else self._music_singles_model
        if page == 3:
            if self.inCollectionView:
                return self._video_model
            if self._video_section == "series":
                return self._video_series_model
            return self._video_my_movies_model
        return self._music_singles_model

    def _collection_list_model(self) -> MediaListModel:
        """Model backing the in-folder list view (album / collection detail)."""
        page = self._current_page
        if page == 2:
            return self._music_model
        if page == 3:
            return self._video_model
        return self._music_model

    def _folder_stack_for_page(self, page: int) -> list[_FolderStackEntry]:
        return {
            2: self._music_folder_stack,
            3: self._video_folder_stack,
        }.get(page, self._music_folder_stack)

    def _make_folder_stack_entry(self, path: Path) -> _FolderStackEntry:
        if self._is_all_musics_virtual(path):
            return _FolderStackEntry(path=path, inode=None)
        resolved = path.resolve() if path.exists() else path
        return _FolderStackEntry(path=resolved, inode=_folder_inode(resolved))

    def _resolve_stack_entry(self, entry: _FolderStackEntry, page: int) -> _FolderStackEntry:
        if self._is_all_musics_virtual(entry.path):
            return entry
        path = entry.path
        if path.exists():
            resolved = path.resolve()
            return _FolderStackEntry(resolved, _folder_inode(resolved) or entry.inode)
        if entry.inode is None:
            return entry

        root = self._root_dir_for_page(page)
        search_roots: list[Path] = []
        try:
            parent = path.parent
            if parent.is_dir():
                search_roots.append(parent)
        except OSError:
            pass
        if root.is_dir() and root not in search_roots:
            search_roots.append(root)

        for search_in in search_roots:
            try:
                children = list(search_in.iterdir())
            except OSError:
                continue
            for child in children:
                if not child.is_dir() or child.name.startswith("."):
                    continue
                try:
                    stat = child.stat()
                except OSError:
                    continue
                if (stat.st_dev, stat.st_ino) != entry.inode:
                    continue
                new_path = child.resolve()
                old_name = path.name
                migrate_metadata(str(path), str(new_path))
                meta = get_metadata(str(new_path))
                if str(meta.get("title") or "").strip() == old_name:
                    set_metadata(str(new_path), title=None)
                return _FolderStackEntry(new_path, entry.inode)
        return entry

    def _reconcile_folder_stack(self, page: int) -> None:
        stack = self._folder_stack_for_page(page)
        changed = False
        for index, entry in enumerate(stack):
            resolved = self._resolve_stack_entry(entry, page)
            if resolved.path != entry.path:
                stack[index] = resolved
                changed = True
        if changed:
            self.libraryNavigationChanged.emit()

    def _root_dir_for_page(self, page: int) -> Path:
        return {
            2: Path(self._music_dir),
            3: Path(self._video_dir),
        }.get(page, Path(self._music_dir))

    def _breadcrumb_for_stack(self, stack: list[_FolderStackEntry]) -> str:
        if not stack:
            return ""
        parts: list[str] = []
        for entry in stack:
            if self._is_all_musics_virtual(entry.path):
                parts.append(ALL_MUSICS_TITLE)
            else:
                parts.append(entry.path.name)
        return " / ".join(parts)

    def _is_all_musics_virtual(self, path: Path | str) -> bool:
        return str(path) == ALL_MUSICS_VIRTUAL_PATH

    def _scan_all_music_tracks(self, *, refresh: bool = False) -> list[MediaInfo]:
        """All audio files under the music library, deduped by canonical path."""
        if not refresh and self._music_track_infos is not None:
            return self._music_track_infos

        seen: set[str] = set()
        tracks: list[MediaInfo] = []
        for info in scan_directory(Path(self._music_dir), AUDIO_EXTS, fast=True):
            key = info.canonical_path or info.path
            if key in seen:
                continue
            seen.add(key)
            tracks.append(info)
        for i, track in enumerate(tracks, start=1):
            track.num = str(i)
        self._music_track_infos = tracks
        return tracks

    def _build_all_musics_collection_item(self, tracks: list[MediaInfo] | None = None) -> dict:
        tracks = tracks if tracks is not None else self._scan_all_music_tracks()
        count = len(tracks)
        music_root = Path(self._music_dir)
        preview_images = find_folder_track_thumbnails(music_root, 4, fast=True)
        if not preview_images:
            folder_image = find_folder_preview_image(music_root, fast=True)
            if folder_image:
                preview_images = [folder_image]
        folder_image = preview_images[0] if preview_images else find_folder_preview_image(music_root, fast=True)
        subtitle = f"{count} bài" if count else "Playlist trống"
        return {
            "title": ALL_MUSICS_TITLE,
            "subtitle": subtitle,
            "path": ALL_MUSICS_VIRTUAL_PATH,
            "canonical_path": ALL_MUSICS_VIRTUAL_PATH,
            "url": ALL_MUSICS_VIRTUAL_PATH,
            "track_id": ALL_MUSICS_VIRTUAL_PATH,
            "duration": "",
            "image": folder_image or "",
            "accent": ACCENT_COLORS[0],
            "audio_only": True,
            "is_remote": False,
            "is_collection": True,
            "kind": MediaKind.ALBUM.name.lower(),
            "child_count": count,
            "preview_images": preview_images,
            "download_percent": 0.0,
            "download_status": "",
            "is_downloading": False,
        }

    @staticmethod
    def _album_path_key(path: Path | str) -> str:
        try:
            return str(Path(path).resolve())
        except OSError:
            return str(path)

    def _build_album_track_search_index(self, tracks: list[MediaInfo] | None = None) -> dict[str, str]:
        """Map album folder path -> lowercase searchable text from contained tracks."""
        if tracks is None:
            tracks = self._scan_all_music_tracks()
        parts: dict[str, list[str]] = {}
        for info in tracks:
            album_key = self._album_path_key(Path(info.path).parent)
            text = f"{info.title.lower()} {(info.artist or '').lower()}"
            parts.setdefault(album_key, []).append(text)
        return {key: " ".join(blob) for key, blob in parts.items()}

    def _enrich_album_search_blobs(
        self,
        albums: list[dict],
        *,
        tracks: list[MediaInfo] | None = None,
    ) -> list[dict]:
        index = self._build_album_track_search_index(tracks)
        all_blob = " ".join(index.values())
        enriched: list[dict] = []
        for album in albums:
            item = dict(album)
            if item.get("is_collection"):
                path = item.get("path", "")
                if self._is_all_musics_virtual(path):
                    item["search_blob"] = all_blob
                else:
                    item["search_blob"] = index.get(self._album_path_key(path), "")
            enriched.append(item)
        return enriched

    def _music_albums_for_root(
        self,
        albums: list[dict],
        *,
        tracks: list[MediaInfo] | None = None,
    ) -> list[dict]:
        tracks = tracks if tracks is not None else self._scan_all_music_tracks()
        virtual = self._build_all_musics_collection_item(tracks)
        return self._enrich_album_search_blobs([virtual, *albums], tracks=tracks)

    def _sync_library_page_view(self, page: int) -> None:
        """Refresh visible models from cached data without rescanning disk."""
        if page == 2:
            stack = self._music_folder_stack
            if self.inSharedPlaylistView:
                playlist = self._music_shared_model.item_at(self._shared_playlist_index)
                if playlist is not None:
                    self._music_model.set_items(self._shared_playlist_track_items(playlist))
            elif stack:
                active = (
                    self._music_albums_model
                    if self._music_section == "albums"
                    else self._music_singles_model
                )
                self._apply_library_filter(self._all_music_items, active)
                self._music_model.set_items(active._items)
            else:
                self._sync_music_root_view()
                self._music_model.set_items(self._music_singles_model._items)
                self._apply_library_filter(self._all_music_shared, self._music_shared_model)
            self.musicSearchChanged.emit()
        elif page == 3:
            stack = self._video_folder_stack
            if stack:
                self._apply_library_filter(self._all_video_items, self.videoModel)
            else:
                self._sync_video_root_view()
                if not self.inSharedSeriesView:
                    self._apply_library_filter(self._all_video_shared, self._video_shared_model)
            self.videoSearchChanged.emit()
        self.libraryNavigationChanged.emit()

    def _current_library_folder(self) -> Path:
        stack = self._folder_stack_for_page(self._current_page)
        if stack:
            top = stack[-1]
            if not self._is_all_musics_virtual(top.path) and not top.path.exists():
                self._reconcile_folder_stack(self._current_page)
                stack = self._folder_stack_for_page(self._current_page)
                top = stack[-1]
            if self._is_all_musics_virtual(top.path):
                return self._root_dir_for_page(self._current_page)
            return top.path
        return self._root_dir_for_page(self._current_page)

    def _library_infos_to_items(self, infos: list[MediaInfo]) -> list[dict]:
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

    def _rebuild_music_root_catalog(
        self,
        *,
        push_to_models: bool = False,
        root_infos: list[MediaInfo] | None = None,
        tracks: list[MediaInfo] | None = None,
    ) -> None:
        """Rescan the music root grid (album cards + singles) from disk."""
        root = Path(self._music_dir)
        if root_infos is None:
            root_infos = self._music_root_infos
        if root_infos is None:
            root_infos = scan_library_folder(root, fast=True)
        self._music_root_infos = root_infos
        root_items = self._library_infos_to_items(root_infos)
        music_tracks = tracks if tracks is not None else self._scan_all_music_tracks()
        # Only seed _music_paths as a default queue when nothing is playing.
        # Otherwise a library hot-reload (e.g. during downloads) would
        # overwrite the active album/playlist queue and break auto-advance.
        if not self._music_paths:
            self._music_paths = [info.path for info in music_tracks]

        # Hide root singles when the same file already lives in a playlist folder.
        in_album = resolved_paths_in_child_folders(root, AUDIO_EXTS)

        self._all_music_singles = [
            item for item in root_items
            if not item.get("is_collection")
            and (item.get("canonical_path") or item.get("path") or "") not in in_album
        ]
        self._all_music_albums = self._music_albums_for_root(
            [item for item in root_items if item.get("is_collection")],
            tracks=music_tracks,
        )
        self._rebuild_all_music_tracks(music_tracks)
        if push_to_models:
            self._sync_music_root_view()

    def _scan_all_video_tracks(self, *, refresh: bool = False) -> list[MediaInfo]:
        if not refresh and self._video_track_infos is not None:
            return self._video_track_infos

        seen: set[str] = set()
        tracks: list[MediaInfo] = []
        for info in scan_directory(Path(self._video_dir), VIDEO_EXTS, fast=True):
            key = info.canonical_path or info.path
            if key in seen:
                continue
            seen.add(key)
            tracks.append(info)
        for i, track in enumerate(tracks, start=1):
            track.num = str(i)
        self._video_track_infos = tracks
        return tracks

    def _rebuild_video_root_catalog(
        self,
        *,
        push_to_models: bool = False,
        root_infos: list[MediaInfo] | None = None,
        tracks: list[MediaInfo] | None = None,
    ) -> None:
        root = Path(self._video_dir)
        if root_infos is None:
            root_infos = self._video_root_infos
        if root_infos is None:
            root_infos = scan_library_folder(root, fast=True)
        self._video_root_infos = root_infos
        root_items = self._library_infos_to_items(root_infos)
        video_tracks = tracks if tracks is not None else self._scan_all_video_tracks()

        in_series = resolved_paths_in_child_folders(root, VIDEO_EXTS)

        self._all_video_my_movies = [
            item for item in root_items
            if not item.get("is_collection")
            and (item.get("canonical_path") or item.get("path") or "") not in in_series
        ]
        self._all_video_movies = []  # Phim lẻ (currently empty, ready for custom logic)
        self._all_video_series = [item for item in root_items if item.get("is_collection")]
        self._all_video_tracks = self._library_infos_to_items(video_tracks)

        if push_to_models:
            self._sync_video_root_view()

    def _sync_video_root_view(self) -> None:
        if self._filter:
            self._apply_video_search()
        else:
            self._video_search_model.set_items([])
            self._apply_library_filter(self._all_video_shared, self._video_shared_model)
            self._apply_library_filter(self._all_video_movies, self._video_movies_model)
            self._apply_library_filter(self._all_video_my_movies, self._video_my_movies_model)
            self._apply_library_filter(
                self._all_video_series,
                self._video_series_model,
                pin_first=False,
            )
        self.videoSearchChanged.emit()

    def _apply_video_search(self) -> None:
        q = self._filter
        if not q:
            self._video_search_model.set_items([])
            return
        filtered = [
            item for item in self._all_video_tracks if self._item_matches_search(item, q)
        ]
        self._video_search_model.set_items(filtered)

    def _reload_library_view(self, page: int) -> None:
        self._reconcile_folder_stack(page)
        stack = self._folder_stack_for_page(page)
        if page == 2 and stack and self._is_all_musics_virtual(stack[-1].path):
            self._rebuild_music_root_catalog(push_to_models=False)
            items = self._library_infos_to_items(self._scan_all_music_tracks())
            self._all_music_items = items
            active = self._music_albums_model if self._music_section == "albums" else self._music_singles_model
            self._apply_library_filter(self._all_music_items, active)
            self._music_model.set_items(active._items)
        else:
            folder = stack[-1].path if stack else self._root_dir_for_page(page)
            root_dir = self._root_dir_for_page(page)
            if page == 2 and not stack and self._music_root_infos is not None and folder == root_dir:
                infos = self._music_root_infos
            elif page == 3 and not stack and self._video_root_infos is not None and folder == root_dir:
                infos = self._video_root_infos
            else:
                infos = scan_library_folder(folder, fast=True)
            items = self._library_infos_to_items(infos)
            if page == 2:
                self._all_music_items = items
                if stack:
                    self._schedule_library_thumbnails(infos)
                    self._rebuild_music_root_catalog(
                        push_to_models=self._current_page == 2 and not self.inCollectionView,
                    )
                    active = self._music_albums_model if self._music_section == "albums" else self._music_singles_model
                    self._apply_library_filter(self._all_music_items, active)
                    self._music_model.set_items(active._items)
                else:
                    self._rebuild_music_root_catalog(push_to_models=True)
                    self._music_model.set_items(self._music_singles_model._items)
            elif page == 3:
                if stack and self._video_section == "series":
                    items = self._load_video_series_items(folder)
                    self._all_video_items = items
                    self._apply_library_filter(self._all_video_items, self._video_model)
                else:
                    infos = scan_library_folder(folder, fast=True)
                    items = self._library_infos_to_items(infos)
                    self._all_video_items = items
                    if stack:
                        self._apply_library_filter(self._all_video_items, self.videoModel)
                    else:
                        self._rebuild_video_root_catalog(push_to_models=self._current_page == 3 and not self.inCollectionView)
        if page == 2:
            self.musicSearchChanged.emit()
        if page == 3:
            self.videoSearchChanged.emit()
        self.libraryNavigationChanged.emit()
        self.playlistOrderUndoChanged.emit()

    def _can_shuffle_collection_order(self) -> bool:
        if self._current_page != 2 or not self.inCollectionView:
            return False
        stack = self._folder_stack_for_page(self._current_page)
        if stack and self._is_all_musics_virtual(stack[-1].path):
            return False
        return self._collection_list_model().rowCount() >= 2

    def _playlist_order_folder_key(self) -> str | None:
        if not self._can_shuffle_collection_order():
            return None
        return str(self._current_library_folder())

    def _apply_collection_order(self, names: list[str]) -> None:
        write_order(self._current_library_folder(), names)
        self._reload_library_view(self._current_page)

    def _clear_playlist_order_undo(self) -> None:
        folder_key = self._playlist_order_folder_key()
        if folder_key is None:
            return
        if folder_key in self._playlist_order_undo:
            del self._playlist_order_undo[folder_key]
            self.playlistOrderUndoChanged.emit()

    def _normalize_download_subdir(self, subdir: str) -> str:
        return (subdir or "").strip().strip("/\\")

    def _active_download_subdir_map(self, media_type: str) -> dict[str, int]:
        if media_type == "music":
            return self._active_music_download_subdirs
        return self._active_video_download_subdirs

    def _track_download_subdir(self, media_type: str, subdir: str) -> None:
        key = self._normalize_download_subdir(subdir)
        counters = self._active_download_subdir_map(media_type)
        counters[key] = counters.get(key, 0) + 1

    def _untrack_download_subdir(self, media_type: str, subdir: str) -> None:
        key = self._normalize_download_subdir(subdir)
        counters = self._active_download_subdir_map(media_type)
        if counters.get(key, 0) <= 1:
            counters.pop(key, None)
        else:
            counters[key] -= 1

    def _merge_tracks_from_active_subdirs(
        self,
        *,
        root: Path,
        subdirs: dict[str, int],
        extensions: set[str],
        existing: list[MediaInfo] | None,
    ) -> list[MediaInfo]:
        from src.scanner import _media_from_file

        tracks = list(existing or [])
        seen = {info.canonical_path or info.path for info in tracks}
        for subdir, count in subdirs.items():
            if count <= 0:
                continue
            if subdir:
                folder = root / subdir
                new_infos = scan_directory(folder, extensions, fast=True) if folder.exists() else []
            elif root.exists():
                new_infos = []
                for f in sorted(root.iterdir()):
                    if not f.is_file():
                        continue
                    ext = f.suffix.lower()
                    if ext not in extensions:
                        continue
                    new_infos.append(
                        _media_from_file(f, audio_only=ext in AUDIO_EXTS, fast=True),
                    )
            else:
                new_infos = []
            for info in new_infos:
                key = info.canonical_path or info.path
                if key in seen:
                    continue
                seen.add(key)
                tracks.append(info)
        for i, track in enumerate(tracks, start=1):
            track.index = i
        return tracks

    def _child_media_paths(
        self,
        root: Path,
        child_names: set[str],
        extensions: set[str],
    ) -> set[str]:
        from src.scanner import _iter_media_files

        paths: set[str] = set()
        for child_name in child_names:
            child = root / child_name
            if not child.is_dir():
                continue
            for media_path in _iter_media_files(child, extensions):
                try:
                    paths.add(str(media_path.resolve()))
                except OSError:
                    paths.add(str(media_path))
        return paths

    def _hotload_video_download_dirs(self, *, push_to_models: bool = False) -> None:
        root = Path(self._video_dir)
        subdirs = self._active_video_download_subdirs
        if not subdirs:
            self._rebuild_video_root_catalog(push_to_models=push_to_models)
            return

        self._video_track_infos = self._merge_tracks_from_active_subdirs(
            root=root,
            subdirs=subdirs,
            extensions=VIDEO_EXTS,
            existing=self._video_track_infos,
        )
        root_items = self._library_infos_to_items(scan_library_folder(root, fast=True))
        top_levels = {
            Path(subdir).parts[0]
            for subdir in subdirs
            if subdir and Path(subdir).parts
        }
        in_series = self._child_media_paths(root, top_levels, VIDEO_EXTS)

        self._all_video_my_movies = [
            item for item in root_items
            if not item.get("is_collection")
            and (item.get("canonical_path") or item.get("path") or "") not in in_series
        ]
        self._all_video_movies = []
        self._all_video_series = [item for item in root_items if item.get("is_collection")]
        self._all_video_tracks = self._library_infos_to_items(self._video_track_infos)
        if push_to_models:
            self._sync_video_root_view()

    def _hotload_music_download_dirs(self, *, push_to_models: bool = False) -> None:
        root = Path(self._music_dir)
        subdirs = self._active_music_download_subdirs
        if not subdirs:
            self._rebuild_music_root_catalog(push_to_models=push_to_models)
            return

        music_tracks = self._merge_tracks_from_active_subdirs(
            root=root,
            subdirs=subdirs,
            extensions=AUDIO_EXTS,
            existing=self._music_track_infos,
        )
        self._music_track_infos = music_tracks
        if not self._music_paths:
            self._music_paths = [info.path for info in music_tracks]

        root_items = self._library_infos_to_items(scan_library_folder(root, fast=True))
        top_levels = {
            Path(subdir).parts[0]
            for subdir in subdirs
            if subdir and Path(subdir).parts
        }
        in_album = self._child_media_paths(root, top_levels, AUDIO_EXTS)

        self._all_music_singles = [
            item for item in root_items
            if not item.get("is_collection")
            and (item.get("canonical_path") or item.get("path") or "") not in in_album
        ]
        self._all_music_albums = self._music_albums_for_root(
            [item for item in root_items if item.get("is_collection")],
            tracks=music_tracks,
        )
        self._rebuild_all_music_tracks(music_tracks)
        if push_to_models:
            self._sync_music_root_view()

    def _hotload_after_download(self, job: _DownloadJob, file_path: str) -> None:
        """Track new files during a batch; catalog refresh is batched by the hotload timer."""
        if job.media_type == "music":
            path = Path(file_path)
            if path.exists() and str(path) not in self._music_paths:
                self._music_paths.append(str(path))

    def _refresh_music_catalog(self) -> None:
        if not self._music_library_loaded:
            self._load_music_library(refresh=True)
            return

        stack = self._folder_stack_for_page(2)
        if stack:
            self._reload_library_view(2)
        elif self._active_music_download_subdirs:
            self._hotload_music_download_dirs(push_to_models=True)
            if self._current_page == 2:
                self._music_model.set_items(self._music_singles_model._items)
        else:
            self._rebuild_music_root_catalog(push_to_models=True)
            if self._current_page == 2:
                self._music_model.set_items(self._music_singles_model._items)
        self.libraryNavigationChanged.emit()

    def _refresh_video_catalog(self) -> None:
        if not self._video_library_loaded and self._pending_video_downloads <= 0:
            return

        if not self._video_library_loaded:
            self._load_video_library(refresh=True)
        else:
            stack = self._folder_stack_for_page(3)
            if stack:
                self._reload_library_view(3)
            elif self._active_video_download_subdirs:
                self._hotload_video_download_dirs(
                    push_to_models=self._current_page == 3 and not self.inCollectionView,
                )
            else:
                self._video_track_infos = None
                self._rebuild_video_root_catalog(
                    push_to_models=self._current_page == 3 and not self.inCollectionView,
                )

        if self._current_page == 3:
            self._sync_library_page_view(3)
        self.libraryNavigationChanged.emit()

    def _downloads_active(self) -> bool:
        if self._download_jobs_in_progress > 0:
            return True
        if self._deferred_403_jobs:
            return True
        queue = self._download_queue
        return queue is not None and not queue.empty()

    def _start_library_hotload_timer(self) -> None:
        interval = (
            _LIBRARY_HOTLOAD_DOWNLOAD_MS
            if self._downloads_active()
            else _LIBRARY_HOTLOAD_MS
        )
        if self._library_hotload_timer.interval() != interval:
            self._library_hotload_timer.setInterval(interval)
        if not self._library_hotload_timer.isActive():
            self._library_hotload_timer.start()

    def _stop_library_hotload_timer(self) -> None:
        self._library_hotload_timer.stop()

    def _on_library_hotload_tick(self) -> None:
        if not self._downloads_active():
            self._stop_library_hotload_timer()
            return
        if self._music_library_loaded:
            self._refresh_music_catalog()
        if self._video_library_loaded or self._pending_video_downloads > 0:
            self._refresh_video_catalog()

    def _rebuild_music_source_ids(self, music_infos: list[MediaInfo]) -> None:
        music_ids: set[str] = set()
        for info in music_infos:
            source_id = resolve_source_id(info.path)
            if source_id:
                music_ids.add(source_id)
        self._music_source_ids = music_ids
        self._music_source_ids_ready = True

    def _rebuild_video_source_ids(self, video_infos: list[MediaInfo]) -> None:
        video_ids: set[str] = set()
        for info in video_infos:
            source_id = resolve_source_id(info.path)
            if source_id:
                video_ids.add(source_id)
        self._video_source_ids = video_ids
        self._video_source_ids_ready = True

    def _ensure_source_ids(self, media_type: str) -> None:
        if media_type == "music":
            if self._music_source_ids_ready:
                return
            if self._music_track_infos is not None:
                self._rebuild_music_source_ids(self._music_track_infos)
                return
            infos = scan_directory(Path(self._music_dir), AUDIO_EXTS, fast=True)
            self._rebuild_music_source_ids(infos)
            return

        if self._video_source_ids_ready:
            return
        if self._video_track_infos is not None:
            self._rebuild_video_source_ids(self._video_track_infos)
            return
        infos = scan_directory(Path(self._video_dir), VIDEO_EXTS, fast=True)
        self._rebuild_video_source_ids(infos)

    def _ensure_music_library_loaded(self) -> None:
        self._load_music_library(refresh=False)

    def _ensure_video_library_loaded(self) -> None:
        self._load_video_library(refresh=False)

    def _start_music_library_scan(self, *, refresh: bool) -> None:
        if self._music_scan_running:
            return
        self._music_scan_running = True
        music_dir = self._music_dir
        cached = self._music_track_infos if not refresh else None

        def _blocking_scan():
            return scan_music_library_bundle(
                Path(music_dir),
                refresh=refresh,
                cached_tracks=cached,
                fast=True,
            )

        loop = asyncio.get_event_loop()
        future = loop.run_in_executor(None, _blocking_scan)

        def _on_done(done_future) -> None:
            try:
                tracks, root_infos = done_future.result()
            except Exception:
                logger.exception("music library scan failed")
                self._music_scan_running = False
                return
            QTimer.singleShot(
                0,
                lambda: self._apply_music_library_scan(tracks, root_infos, refresh=refresh),
            )

        future.add_done_callback(_on_done)

    def _start_video_library_scan(self, *, refresh: bool) -> None:
        if self._video_scan_running:
            return
        self._video_scan_running = True
        video_dir = self._video_dir
        cached = self._video_track_infos if not refresh else None

        def _blocking_scan():
            return scan_video_library_bundle(
                Path(video_dir),
                refresh=refresh,
                cached_tracks=cached,
                fast=True,
            )

        loop = asyncio.get_event_loop()
        future = loop.run_in_executor(None, _blocking_scan)

        def _on_done(done_future) -> None:
            try:
                tracks, root_infos = done_future.result()
            except Exception:
                logger.exception("video library scan failed")
                self._video_scan_running = False
                return
            QTimer.singleShot(
                0,
                lambda: self._apply_video_library_scan(tracks, root_infos, refresh=refresh),
            )

        future.add_done_callback(_on_done)

    def _apply_music_library_scan(
        self,
        music_infos: list[MediaInfo],
        root_infos: list[MediaInfo],
        *,
        refresh: bool,
    ) -> None:
        self._music_scan_running = False
        self._music_track_infos = music_infos
        self._music_root_infos = root_infos
        if not self._music_paths:
            self._music_paths = [info.path for info in music_infos]
        self._reload_library_view(2)
        self._music_library_loaded = True
        self._schedule_library_thumbnails(music_infos + root_infos)
        self._schedule_source_id_rebuild("music", music_infos)

        def _finalize() -> None:
            if self._current_page == 2:
                self._sync_library_page_view(2)
            if refresh:
                self._drop_missing_current_track()

        QTimer.singleShot(0, _finalize)

        preview_limit = 12
        self._media_music_preview = self._library_infos_to_items(music_infos)[:preview_limit]
        self.mediaMusicModel.set_items(self._media_music_preview)

    def _apply_video_library_scan(
        self,
        video_infos: list[MediaInfo],
        root_infos: list[MediaInfo],
        *,
        refresh: bool,
    ) -> None:
        self._video_scan_running = False
        self._video_track_infos = video_infos
        self._video_root_infos = root_infos
        self._reload_library_view(3)
        self._video_library_loaded = True
        self._schedule_library_thumbnails(video_infos + root_infos)
        self._schedule_source_id_rebuild("video", video_infos)

        def _finalize() -> None:
            if self._current_page == 3:
                self._sync_library_page_view(3)
            if refresh:
                self._drop_missing_current_track()

        QTimer.singleShot(0, _finalize)

        preview_limit = 12
        self._media_video_preview = self._library_infos_to_items(video_infos)[:preview_limit]
        self.mediaVideoModel.set_items(self._media_video_preview)

    def _schedule_source_id_rebuild(self, media_type: str, infos: list[MediaInfo]) -> None:
        """Resolve YouTube source ids off the UI thread (mutagen + metadata writes)."""
        paths = [info.path for info in infos if info.path]

        def _blocking_rebuild() -> set[str]:
            ids: set[str] = set()
            for path in paths:
                source_id = resolve_source_id(path, cache=True)
                if source_id:
                    ids.add(source_id)
            return ids

        loop = asyncio.get_event_loop()
        future = loop.run_in_executor(None, _blocking_rebuild)

        def _on_done(done_future) -> None:
            try:
                ids = done_future.result()
            except Exception:
                logger.debug("source id rebuild failed for %s", media_type, exc_info=True)
                return

            def _apply() -> None:
                if media_type == "music":
                    self._music_source_ids = ids
                    self._music_source_ids_ready = True
                else:
                    self._video_source_ids = ids
                    self._video_source_ids_ready = True

            QTimer.singleShot(0, _apply)

        future.add_done_callback(_on_done)

    def _on_thumbnail_queue_ready(self, path: str, image: str, is_folder: bool) -> None:
        preview = [image] if is_folder else None
        self._apply_library_thumbnail(path, image, preview_images=preview)
        if is_folder:
            self._refresh_root_collection_grids()

    def _refresh_root_collection_grids(self) -> None:
        """Re-bind root playlist/series grids after artwork arrives."""
        if self._current_page == 2 and not self.inCollectionView and not self.inSharedPlaylistView:
            self._apply_library_filter(
                self._all_music_albums,
                self._music_albums_model,
                pin_first=True,
            )
        elif self._current_page == 3 and not self.inCollectionView and not self.inSharedSeriesView:
            self._apply_library_filter(
                self._all_video_series,
                self._video_series_model,
                pin_first=False,
            )

    def _schedule_library_thumbnails(self, infos: list[MediaInfo]) -> None:
        """Fill missing card artwork in the background after a fast scan."""
        queue = get_thumbnail_queue()
        scheduled: set[str] = set()

        for info in infos:
            path = info.canonical_path or info.path
            if not path or path in scheduled:
                continue
            if info.image:
                continue
            if info.kind != MediaKind.FILE:
                scheduled.add(path)
                queue.submit_folder_preview(path)
                continue
            ext = Path(path).suffix.lower()
            if not ext:
                continue
            scheduled.add(path)
            queue.submit(path, is_video=ext in VIDEO_EXTS)

    def _apply_library_thumbnail(
        self,
        path: str,
        image: str,
        *,
        preview_images: list[str] | None = None,
    ) -> None:
        try:
            resolved = str(Path(path).resolve())
        except OSError:
            resolved = path
        path_keys = {path, resolved}

        models = (
            self._music_model,
            self._music_singles_model,
            self._music_albums_model,
            self._music_search_model,
            self._music_shared_model,
            self.mediaMusicModel,
            self._video_model,
            self._video_series_model,
            self._video_movies_model,
            self._video_my_movies_model,
            self._video_shared_model,
            self._video_search_model,
            self.mediaVideoModel,
        )
        for model in models:
            model.update_image_by_path(path, image, preview_images=preview_images)
            if resolved != path:
                model.update_image_by_path(resolved, image, preview_images=preview_images)

        for collection in (
            self._all_music_items,
            self._all_music_singles,
            self._all_music_albums,
            self._all_music_tracks,
            self._all_video_items,
            self._all_video_tracks,
            self._media_music_preview,
            self._media_video_preview,
        ):
            for item in collection:
                item_path = str(item.get("canonical_path") or item.get("path") or "")
                try:
                    item_resolved = str(Path(item_path).resolve()) if item_path else ""
                except OSError:
                    item_resolved = item_path
                if item_path not in path_keys and item_resolved not in path_keys:
                    continue
                item["image"] = image
                if preview_images is not None:
                    item["preview_images"] = list(preview_images)

        for info in (self._music_track_infos or []) + (self._video_track_infos or []):
            info_path = info.canonical_path or info.path
            try:
                info_resolved = str(Path(info_path).resolve()) if info_path else ""
            except OSError:
                info_resolved = info_path
            if info_path in path_keys or info_resolved in path_keys:
                info.image = image
                if preview_images is not None:
                    info.preview_images = list(preview_images)

    def _load_music_library(self, *, refresh: bool = False) -> None:
        if self._music_library_loaded and not refresh:
            return
        if refresh:
            self._music_root_infos = None
            self._music_track_infos = None
        self._start_music_library_scan(refresh=refresh)

    def _load_video_library(self, *, refresh: bool = False) -> None:
        if self._video_library_loaded and not refresh:
            return
        if refresh:
            self._video_root_infos = None
            self._video_track_infos = None
        self._start_video_library_scan(refresh=refresh)

    def _reload_current_library(self, *, refresh: bool = True) -> None:
        if self._current_page == 2:
            self._load_music_library(refresh=refresh)
        elif self._current_page == 3:
            self._load_video_library(refresh=refresh)

    def _reset_libraries_for_storage_change(self) -> None:
        music_was_loaded = self._music_library_loaded
        video_was_loaded = self._video_library_loaded

        self._music_library_loaded = False
        self._video_library_loaded = False
        self._music_track_infos = None
        self._video_track_infos = None
        self._music_root_infos = None
        self._video_root_infos = None
        self._music_scan_running = False
        self._video_scan_running = False
        self._music_source_ids = set()
        self._video_source_ids = set()
        self._music_source_ids_ready = False
        self._video_source_ids_ready = False
        self._all_music_items = []
        self._all_music_singles = []
        self._all_music_albums = []
        self._all_music_tracks = []
        self._all_video_items = []
        self._music_paths = []
        self._media_music_preview = []
        self._media_video_preview = []
        self.mediaMusicModel.set_items([])
        self.mediaVideoModel.set_items([])

        if music_was_loaded:
            self._load_music_library(refresh=True)
            if self._current_page == 2:
                self._sync_library_page_view(2)
        if video_was_loaded:
            self._load_video_library(refresh=True)
            if self._current_page == 3:
                self._sync_library_page_view(3)

    def _annotate_search_results(self, items: list[dict], media_type: str) -> list[dict]:
        self._ensure_source_ids(media_type)
        pool = self._music_source_ids if media_type == "music" else self._video_source_ids
        annotated: list[dict] = []
        for item in items:
            row = dict(item)
            video_id = str(item.get("id") or "")
            if not video_id:
                video_id = extract_youtube_id(str(item.get("url") or ""))
            row["in_library"] = bool(video_id and video_id in pool)
            annotated.append(row)
        return annotated

    def _item_matches_search(self, item: dict, q: str) -> bool:
        if q in item["title"].lower() or q in item["subtitle"].lower():
            return True
        if item.get("is_collection"):
            return q in item.get("search_blob", "")
        return False

    def _rebuild_all_music_tracks(self, tracks: list[MediaInfo] | None = None) -> None:
        if tracks is None:
            tracks = self._scan_all_music_tracks()
        self._all_music_tracks = self._library_infos_to_items(tracks)

    def _apply_music_search(self) -> None:
        q = self._filter
        if not q:
            self._music_search_model.set_items([])
            return
        filtered = [
            item for item in self._all_music_tracks if self._item_matches_search(item, q)
        ]
        self._music_search_model.set_items(filtered)

    def _sync_music_root_view(self) -> None:
        if self._filter:
            self._apply_music_search()
        else:
            self._music_search_model.set_items([])
            self._apply_library_filter(self._all_music_singles, self._music_singles_model)
            self._apply_library_filter(
                self._all_music_albums,
                self._music_albums_model,
                pin_first=True,
            )
        self.musicSearchChanged.emit()

    def _apply_library_filter(
        self,
        source: list[dict],
        model: MediaListModel,
        *,
        pin_first: bool = False,
    ) -> None:
        q = self._filter
        pinned: dict | None = None
        pool = source
        if pin_first and source and self._is_all_musics_virtual(source[0].get("path", "")):
            pinned = source[0]
            pool = source[1:]
        if not q:
            model.set_items(([pinned] if pinned else []) + pool)
            return
        if pinned and not self._item_matches_search(pinned, q):
            pinned = None
        filtered = [item for item in pool if self._item_matches_search(item, q)]
        model.set_items(([pinned] if pinned else []) + filtered)

    def _collection_media_items(self) -> list[dict]:
        if not self.inCollectionView:
            return []
        model = self._collection_list_model()
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
        self._music_paths = []
        self._playback_items = {}
        seen_canonical: set[str] = set()
        for item in items:
            path = item.get("path") or item.get("url") or ""
            if not path:
                continue
            canonical = item.get("canonical_path") or path
            if canonical in seen_canonical:
                continue
            seen_canonical.add(canonical)
            self._music_paths.append(path)
            self._playback_items[path] = item

    def _set_track_thumbnail(self, image: str) -> None:
        image = image or ""
        if self._track_thumbnail != image:
            self._track_thumbnail = image
            self.trackThumbnailChanged.emit()
            # Persist for next-launch restore if we already have a playing session
            if self._has_played_before and self._is_playing:
                save_raw_state({"last_track_thumbnail": image})

    def _image_for_path(self, path: str, *, audio_only: bool) -> str:
        if not path or _is_remote(path):
            return ""
        for pool in (
            self._playback_items.values(),
            self._all_music_items,
            self._all_video_items,
            self._music_model._items,
            self._music_singles_model._items,
            self._music_albums_model._items,
            self._video_model._items,
            self._media_music_model._items,
            self._media_video_model._items,
        ):
            for item in pool:
                item_path = item.get("path") or item.get("url") or ""
                if item_path != path:
                    continue
                image = item.get("image") or item.get("thumbnail_url") or ""
                if image:
                    return image
        media_path = Path(path)
        if not media_path.exists():
            return ""
        if audio_only:
            embedded = read_embedded_metadata(media_path)
            default_image = embedded.get("image", "")
        else:
            default_image = read_video_thumbnail(media_path)
        return resolve_display(
            str(media_path.resolve()),
            default_title=media_path.stem,
            default_image=default_image,
        ).get("image", "")

    def _start_playback(
        self,
        path: str,
        *,
        audio_only: bool,
        title: str = "",
        artist: str = "",
        start_pos: float = 0.0,
    ) -> None:
        # This is a final guard for every backend call path (including resume
        # from the player bar): video must never be delegated to an external
        # mpv window.  It is rendered by FocusModeScreen in the main QML window.
        if not audio_only:
            self._set_current_path(path)
            self._current_audio_only = False
            self.enterFocusMode(path, title)
            return
        self._player.play(
            path,
            title=title,
            artist=artist,
            volume=self._volume,
            muted=self._muted,
            start_pos=start_pos,
        )

    def _play_item(self, item: dict) -> None:
        path = item.get("path") or item.get("url") or ""
        if not path:
            return
        audio_only = item.get("audio_only", True)
        title = item.get("title", "")
        artist = item.get("subtitle", "")

        # Qt Multimedia owns all video rendering inside the QML window.
        if not audio_only:
            self._set_current_path(path)
            self._current_audio_only = False
            self._start_playback(path, audio_only=False, title=title)
            return

        self._sync_player_bar_for_media(audio_only)

        thumbnail = item.get("image") or item.get("thumbnail_url") or ""
        if thumbnail:
            self._set_track_thumbnail(thumbnail)

        if _is_remote(path):
            if not self._is_online:
                return
            self._set_current_path(path)
            self._current_audio_only = audio_only
            self._start_playback(
                path, audio_only=audio_only, title=title, artist=artist
            )
            if not thumbnail:
                QTimer.singleShot(
                    0,
                    lambda p=path, ao=audio_only: self._deferred_thumbnail(p, ao),
                )
            return

        self._set_current_path(path)
        self._current_audio_only = audio_only
        self._start_playback(path, audio_only=audio_only, title=title, artist=artist)
        if not thumbnail:
            QTimer.singleShot(
                0,
                lambda p=path, ao=audio_only: self._deferred_thumbnail(p, ao),
            )

    def _deferred_thumbnail(self, path: str, audio_only: bool) -> None:
        if self._current_path != path:
            return
        thumbnail = self._image_for_path(path, audio_only=audio_only)
        if thumbnail:
            self._set_track_thumbnail(thumbnail)

    def _music_index(self) -> int:
        if not self._current_path:
            return -1
        try:
            return self._music_paths.index(self._current_path)
        except ValueError:
            pass

        try:
            curr_resolved = str(Path(self._current_path).resolve())
            resolved_paths = [str(Path(p).resolve()) if not _is_remote(p) else p for p in self._music_paths]
            return resolved_paths.index(curr_resolved)
        except Exception:
            return -1

    def _play_path(self, path: str) -> None:
        queued = self._playback_items.get(path)
        audio_only = bool(queued.get("audio_only", True)) if queued else True
        title = (queued or {}).get("title", "")
        artist = (queued or {}).get("subtitle", "")

        self._set_current_path(path)
        self._current_audio_only = audio_only
        self._sync_player_bar_for_media(audio_only)

        thumbnail = ""
        if queued:
            thumbnail = queued.get("image") or queued.get("thumbnail_url") or ""
        if thumbnail:
            self._set_track_thumbnail(thumbnail)

        self._start_playback(
            path, audio_only=audio_only, title=title, artist=artist
        )
        if not thumbnail and not _is_remote(path):
            QTimer.singleShot(
                0,
                lambda p=path, ao=audio_only: self._deferred_thumbnail(p, ao),
            )

    def _play_adjacent(self, delta: int) -> None:
        if not self._music_paths:
            return

        idx = self._music_index()
        if idx < 0:
            if delta > 0:
                idx = 0
            else:
                idx = len(self._music_paths) - 1
        elif delta > 0:
            next_idx = idx + 1
            if next_idx >= len(self._music_paths):
                if self._loop_mode == 1:
                    next_idx = 0
                else:
                    return
            idx = next_idx
        else:
            if idx == 0:
                if self._loop_mode == 1:
                    idx = len(self._music_paths) - 1
                else:
                    return
            else:
                idx = idx - 1

        self._play_path(self._music_paths[idx])

    def _play_random_other(self) -> None:
        if len(self._music_paths) <= 1:
            if self._loop_mode >= 1 and self._music_paths:
                self._play_path(self._music_paths[0])
            return

        candidates = [p for p in self._music_paths if p != self._current_path]
        if candidates:
            self._play_path(random.choice(candidates))

    def _on_track_ended(self) -> None:
        if not self._current_path:
            return
        if self._in_focus_mode:
            self.exitFocusMode()
            return
        if self._loop_mode == 2:
            self._play_path(self._current_path)
        elif self._shuffle_on:
            self._play_random_other()
        else:
            self._play_adjacent(1)

    def _show_player_bar(self) -> None:
        if self._current_path and not _track_path_available(self._current_path):
            return
        if not self._player_bar_visible:
            self._player_bar_visible = True
            self.playerBarVisibleChanged.emit()

    def _hide_player_bar(self) -> None:
        if self._player_bar_visible:
            self._player_bar_visible = False
            self.playerBarVisibleChanged.emit()

    def _sync_player_bar_for_media(self, audio_only: bool) -> None:
        if self._player_bar_always_visible:
            self._show_player_bar()
            return
        if audio_only:
            self._show_player_bar()
        else:
            self._hide_player_bar()

    def _schedule_player_bar_hide(self) -> None:
        if self._player_bar_always_visible or self._has_played_before:
            return
        self._player_bar_idle_timer.start()

    def _cancel_player_bar_hide(self) -> None:
        self._player_bar_idle_timer.stop()

    def _touch_player_bar(self) -> None:
        if not self._current_audio_only and self._is_playing:
            return
        self._show_player_bar()
        if not self._is_playing:
            self._schedule_player_bar_hide()

    def _on_player_bar_idle_timeout(self) -> None:
        # Only hide the bar if the user has never played anything in any session.
        if self._has_played_before or self._player_bar_always_visible:
            return
        if self._is_playing:
            return
        if self._player_bar_visible:
            self._player_bar_visible = False
            self.playerBarVisibleChanged.emit()

    def _drop_missing_current_track(self) -> bool:
        if not self._current_path or _track_path_available(self._current_path):
            return False
        self._clear_current_track()
        return True

    def _clear_current_track(self) -> None:
        self._player.stop()
        self._set_current_path("")
        self._current_audio_only = True
        self._track_title = "LIMINAL"
        self._track_artist = "Offline Media Player"
        self._set_track_thumbnail("")
        if self._position != 0.0:
            self._position = 0.0
            self.positionChanged.emit()
        if self._duration != 0.0:
            self._duration = 0.0
            self.durationChanged.emit()
        if self._is_playing:
            self._is_playing = False
            self.isPlayingChanged.emit()
        if self._has_media:
            self._has_media = False
            self.hasMediaChanged.emit()
        self._hide_player_bar()
        self.trackTitleChanged.emit()
        self.trackArtistChanged.emit()
        save_raw_state({
            "last_track_title": "",
            "last_track_artist": "",
            "last_track_thumbnail": "",
            "last_track_path": "",
            "last_track_audio_only": True,
            "last_track_position": 0.0,
        })

    def _on_state_changed(self, state) -> None:
        if self._drop_missing_current_track():
            return

        # When STOPPED, state.path still holds the just-ended track.
        # Don't let it overwrite _current_path which _play_path already
        # updated to the new track during auto-advance.
        if state.path and state.status != PlaybackStatus.STOPPED:
            self._set_current_path(state.path)
            path_lower = state.path.lower()
            self._current_audio_only = (
                any(path_lower.endswith(ext) for ext in AUDIO_EXTS)
                or _is_remote(state.path)
            )

        if state.title and state.title != "Nothing playing":
            self._track_title = state.title[:40]
            self._track_artist = (
                f"•  {state.artist}" if state.artist != "—" else "Offline Media Player"
            )
        elif not self._current_path:
            self._track_title = "LIMINAL"
            self._track_artist = "Offline Media Player"
            self._set_track_thumbnail("")

        playing = state.status == PlaybackStatus.PLAYING
        if self._is_playing != playing:
            self._is_playing = playing
            self.isPlayingChanged.emit()

        if playing:
            self._cancel_player_bar_hide()
            if self._current_audio_only or self._player_bar_always_visible:
                self._show_player_bar()
            else:
                self._hide_player_bar()
            # Mark first-ever play and persist session info
            if not self._has_played_before:
                self._has_played_before = True
                save_raw_state({"has_played_before": True})
            save_raw_state({
                "last_track_title":      self._track_title,
                "last_track_artist":     self._track_artist,
                "last_track_thumbnail":  self._track_thumbnail,
                "last_track_path":       self._current_path,
                "last_track_audio_only": self._current_audio_only,
                "last_track_position":   self._position,
            })
        else:
            # Only arm the hide-timer before the user has ever played anything
            if not self._has_played_before:
                self._schedule_player_bar_hide()
            else:
                self._cancel_player_bar_hide()
                if not self._player_bar_always_visible and _track_path_available(
                    self._current_path
                ):
                    self._show_player_bar()
            # When paused or stopped, save position
            if (
                self._has_played_before
                and self._current_path
                and _track_path_available(self._current_path)
            ):
                save_raw_state({
                    "last_track_position":   self._position,
                })

        has_media = (state.status != PlaybackStatus.STOPPED) or _track_path_available(
            self._current_path
        )
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
        if getattr(self, "_cleaned_up", False):
            return
        self._cleaned_up = True
        self._video_progress_timer.stop()
        self._save_video_progress()
        if self._has_played_before and self._current_path:
            try:
                save_raw_state({
                    "last_track_position": self._position
                })
            except Exception as e:
                logger.warning("Failed to save last track position: %s", e)
        self._player.cleanup_sync()

    def _set_current_path(self, path: str) -> None:
        if self._current_path != path:
            self._current_path = path
