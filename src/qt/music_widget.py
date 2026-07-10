"""Spotify-inspired music browser widget."""

from __future__ import annotations

import random
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.config import MUSIC_DIR
from src.models import PlaybackStatus, PlaybackState
from src.player import PlayerBridge
from src.scanner import scan_music


def _fmt_time(seconds: float) -> str:
    if seconds <= 0:
        return "0:00"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


class MusicWidget(QWidget):
    request_settings = pyqtSignal()

    def __init__(self, player: PlayerBridge, parent=None):
        super().__init__(parent)
        self._player = player
        self._all_tracks = scan_music()
        self._filtered_indices: list[int] = list(range(len(self._all_tracks)))
        self._shuffle_on = False
        self._loop_on = False

        self._building = True  # suppress signals during setup

        self._build_ui()
        self._connect_signals()
        self._populate_tracks()

        self._building = False
        self._update_header()

    # ── UI construction ──

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Sidebar ──
        sidebar = QVBoxLayout()
        sidebar.setContentsMargins(0, 8, 0, 8)
        sidebar.setSpacing(4)

        btn_library = QPushButton("▶  Library")
        btn_library.setCheckable(True)
        btn_library.setChecked(True)
        sidebar.addWidget(btn_library)
        self._nav_library = btn_library

        btn_playlists = QPushButton("\U0001f4cb  Playlists")
        sidebar.addWidget(btn_playlists)
        self._nav_playlists = btn_playlists

        btn_settings = QPushButton("⚙  Settings")
        btn_settings.clicked.connect(self.request_settings.emit)
        sidebar.addWidget(btn_settings)

        sidebar.addStretch()

        count = QLabel(f"Tracks: {len(self._all_tracks)}")
        count.setObjectName("track-count-label")
        sidebar.addWidget(count)
        self._track_count_label = count

        sidebar_widget = QWidget()
        sidebar_widget.setObjectName("sidebar")
        sidebar_widget.setLayout(sidebar)
        root.addWidget(sidebar_widget)

        # ── Content ──
        content = QVBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(0)

        # Search bar
        search = QLineEdit()
        search.setPlaceholderText("Search tracks, artists...")
        search.textChanged.connect(self._on_filter)
        content.addWidget(search)
        self._search = search

        # Header
        header = QLabel()
        header.setObjectName("content-header")
        content.addWidget(header)
        self._content_header = header

        # Track table
        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["#", "Title", "Artist", "Duration"])
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
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(3, 70)
        content.addWidget(table)
        self._table = table

        content_widget = QWidget()
        content_widget.setLayout(content)
        root.addWidget(content_widget, 1)

    # ── Track population ──

    def _populate_tracks(self) -> None:
        table = self._table
        table.setRowCount(len(self._all_tracks))
        for i, t in enumerate(self._all_tracks):
            table.setItem(i, 0, QTableWidgetItem(t.num))
            table.setItem(i, 1, QTableWidgetItem(t.title))
            table.setItem(i, 2, QTableWidgetItem(t.artist))
            table.setItem(i, 3, QTableWidgetItem(t.duration))

    def _update_header(self) -> None:
        n = len(self._filtered_indices)
        s = "s" if n != 1 else ""
        self._content_header.setText(f"{n} song{s}")

    # ── Filter ──

    def _on_filter(self, text: str) -> None:
        query = text.strip().lower()
        table = self._table
        self._filtered_indices = []
        for i, t in enumerate(self._all_tracks):
            match = (not query) or query in t.title.lower() or query in t.artist.lower()
            table.setRowHidden(i, not match)
            if match:
                self._filtered_indices.append(i)
        self._update_header()

    # ── Playback ──

    def _real_index(self) -> int:
        sel = self._table.currentRow()
        if sel < 0 or sel >= len(self._all_tracks):
            return -1
        return sel

    def _play_selected(self) -> None:
        real = self._real_index()
        if real >= 0:
            self._player.play(self._all_tracks[real].path, audio_only=True)

    def _on_row_double_clicked(self) -> None:
        self._play_selected()

    def _on_track_ended(self) -> None:
        if not self._filtered_indices:
            return
        n = len(self._filtered_indices)
        visible = [i for i in range(self._table.rowCount()) if not self._table.isRowHidden(i)]
        if not visible:
            return
        cur = self._table.currentRow()
        try:
            idx = visible.index(cur)
        except ValueError:
            idx = 0

        if self._shuffle_on:
            candidates = [i for i in range(n) if i != idx]
            if candidates:
                idx = random.choice(candidates)
        else:
            idx = (idx + 1) % n
            if not self._loop_on and idx == 0:
                return

        if idx < len(visible):
            self._table.selectRow(visible[idx])
            real = self._real_index()
            if real >= 0:
                self._player.play(self._all_tracks[real].path, audio_only=True)

    def _play_next(self) -> None:
        self._on_track_ended()

    def _play_prev(self) -> None:
        visible = [i for i in range(self._table.rowCount()) if not self._table.isRowHidden(i)]
        if not visible:
            return
        cur = self._table.currentRow()
        try:
            idx = visible.index(cur)
        except ValueError:
            idx = 0
        idx = (idx - 1) % len(visible)
        self._table.selectRow(visible[idx])
        real = self._real_index()
        if real >= 0:
            self._player.play(self._all_tracks[real].path, audio_only=True)

    def _toggle_shuffle(self) -> None:
        self._shuffle_on = not self._shuffle_on

    def _toggle_loop(self) -> None:
        self._loop_on = not self._loop_on

    # ── Signal connections ──

    def _connect_signals(self) -> None:
        self._player.state_changed.connect(self._on_state_changed)
        self._player.position_changed.connect(self._on_position_changed)
        self._player.track_ended.connect(self._on_track_ended)

    def _on_state_changed(self, state: PlaybackState) -> None:
        if self._building:
            return

    def _on_position_changed(self, time_pos: float, duration: float) -> None:
        if self._building:
            return

    # ── Focus ──

    def focus_search(self) -> None:
        self._search.setFocus()
