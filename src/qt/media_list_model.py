"""QAbstractListModel for GridView media cards in QML."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import (
    QAbstractListModel,
    QModelIndex,
    QObject,
    Qt,
    pyqtProperty,
    pyqtSignal,
    pyqtSlot,
)

ACCENT_COLORS = [
    "#6366f1", "#8b5cf6", "#ec4899", "#f43f5e", "#f97316",
    "#eab308", "#22c55e", "#14b8a6", "#06b6d4", "#3b82f6",
]


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
    CategoryRole = Qt.ItemDataRole.UserRole + 22
    CategoryLabelRole = Qt.ItemDataRole.UserRole + 23

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
            self.CategoryRole: "category",
            self.CategoryLabelRole: "category_label",
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
            self.CategoryRole: b"category",
            self.CategoryLabelRole: b"categoryLabel",
        }

    def set_items(self, items: list[dict]) -> None:
        self.beginResetModel()
        self._items = items
        self.endResetModel()
        self.countChanged.emit()

    @pyqtSlot(int, result="QVariant")
    def item_at(self, row: int) -> dict | None:
        if 0 <= row < len(self._items):
            return self._items[row]
        return None

    @pyqtSlot(int, result="QVariant")
    def itemAt(self, row: int):
        """QML-friendly accessor used by section grouping helpers."""
        return self.item_at(row)

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
