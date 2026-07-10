"""Video browser widget."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QSlider,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.models import PlaybackStatus, PlaybackState
from src.player import PlayerBridge
from src.scanner import scan_video


def _fmt_time(seconds: float) -> str:
    if seconds <= 0:
        return "0:00"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


class VideoWidget(QWidget):

    def __init__(self, player: PlayerBridge, parent=None):
        super().__init__(parent)
        self._player = player
        self._all_videos = scan_video()
        self._filtered_indices: list[int] = list(range(len(self._all_videos)))
        self._building = True

        self._build_ui()
        self._connect_signals()
        self._populate_videos()

        self._building = False
        self._update_header()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Search bar
        search = QLineEdit()
        search.setPlaceholderText("Filter videos...")
        search.textChanged.connect(self._on_filter)
        layout.addWidget(search)
        self._search = search

        # Header
        header = QLabel()
        header.setObjectName("content-header")
        layout.addWidget(header)
        self._content_header = header

        # Video table
        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["#", "Title", "Duration"])
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)
        table.verticalHeader().hide()
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.doubleClicked.connect(self._on_row_double_clicked)
        table.horizontalHeader().setStretchLastSection(False)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(0, 40)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(2, 70)
        layout.addWidget(table)
        self._table = table

    def _populate_videos(self) -> None:
        table = self._table
        table.setRowCount(len(self._all_videos))
        for i, v in enumerate(self._all_videos):
            table.setItem(i, 0, QTableWidgetItem(v.num))
            table.setItem(i, 1, QTableWidgetItem(v.title))
            table.setItem(i, 2, QTableWidgetItem(v.duration))

    def _update_header(self) -> None:
        n = len(self._filtered_indices)
        s = "s" if n != 1 else ""
        self._content_header.setText(f"VIDEO LIBRARY — {n} file{s}")

    def _on_filter(self, text: str) -> None:
        query = text.strip().lower()
        table = self._table
        self._filtered_indices = []
        for i, v in enumerate(self._all_videos):
            match = (not query) or query in v.title.lower()
            table.setRowHidden(i, not match)
            if match:
                self._filtered_indices.append(i)
        self._update_header()

    def _real_index(self) -> int:
        sel = self._table.currentRow()
        if sel < 0 or sel >= len(self._all_videos):
            return -1
        return sel

    def _play_selected(self) -> None:
        real = self._real_index()
        if real >= 0:
            self._player.play(self._all_videos[real].path, audio_only=False)

    def _on_row_double_clicked(self) -> None:
        self._play_selected()

    def _connect_signals(self) -> None:
        self._player.state_changed.connect(self._on_state_changed)
        self._player.position_changed.connect(self._on_position_changed)

    def _on_state_changed(self, state: PlaybackState) -> None:
        pass  # handled by MainWindow's now-playing bar

    def _on_position_changed(self, time_pos: float, duration: float) -> None:
        pass  # handled by MainWindow's now-playing bar

    def focus_search(self) -> None:
        self._search.setFocus()
