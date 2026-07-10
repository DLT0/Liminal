"""Main application window with sidebar navigation and now-playing bar."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.models import PlaybackStatus, PlaybackState
from src.player import PlayerBridge
from src.qt.home_widget import HomeWidget
from src.qt.music_widget import MusicWidget
from src.qt.playlist_widget import PlaylistWidget
from src.qt.settings_widget import SettingsWidget
from src.qt.styles import STYLESHEET
from src.qt.video_widget import VideoWidget


def _fmt_time(seconds: float) -> str:
    if seconds <= 0:
        return "0:00"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


PAGE_HOME = 0
PAGE_MUSIC = 1
PAGE_VIDEO = 2
PAGE_PLAYLISTS = 3
PAGE_SETTINGS = 4


class MainWindow(QMainWindow):

    def __init__(self, player: PlayerBridge) -> None:
        super().__init__()
        self._player = player
        self._current_page = PAGE_HOME
        self._seeking = False

        self.setWindowTitle("Liminal")
        self.setMinimumSize(900, 600)
        self.resize(1100, 720)
        self.setStyleSheet(STYLESHEET)

        self._build_ui()
        self._connect_signals()
        self._setup_shortcuts()

    # ── UI construction ──

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Body: sidebar + stack ──
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        # Sidebar
        sidebar = QVBoxLayout()
        sidebar.setContentsMargins(0, 12, 0, 12)
        sidebar.setSpacing(2)

        self._nav_group = QButtonGroup(self)
        self._nav_group.setExclusive(True)

        nav_home = self._make_nav("Home", PAGE_HOME)
        nav_music = self._make_nav("\U0001f3b5  Music", PAGE_MUSIC)
        nav_music.setObjectName("nav-music")
        nav_video = self._make_nav("\U0001f4fa  Video", PAGE_VIDEO)
        nav_video.setObjectName("nav-video")
        nav_playlists = self._make_nav("\U0001f4cb  Playlists", PAGE_PLAYLISTS)
        nav_settings = self._make_nav("⚙  Settings", PAGE_SETTINGS)

        self._nav_buttons = [nav_home, nav_music, nav_video, nav_playlists, nav_settings]

        for btn in self._nav_buttons:
            sidebar.addWidget(btn)

        sidebar.addStretch()

        sidebar_widget = QWidget()
        sidebar_widget.setObjectName("sidebar")
        sidebar_widget.setLayout(sidebar)
        body.addWidget(sidebar_widget)

        # Stacked content area
        self._stack = QStackedWidget()

        self._home = HomeWidget()
        self._music = MusicWidget(self._player)
        self._video = VideoWidget(self._player)
        self._playlists = PlaylistWidget()
        self._settings = SettingsWidget()

        self._stack.addWidget(self._home)       # 0
        self._stack.addWidget(self._music)      # 1
        self._stack.addWidget(self._video)      # 2
        self._stack.addWidget(self._playlists)  # 3
        self._stack.addWidget(self._settings)   # 4

        body.addWidget(self._stack, 1)
        root.addLayout(body, 1)

        # ── Now-playing bar ──
        root.addWidget(self._build_nowplaying())

        # ── Wire home widget navigation ──
        self._home.navigate.connect(self._on_home_navigate)
        self._music.request_settings.connect(lambda: self._switch_page(PAGE_SETTINGS))

        # Start on home
        self._switch_page(PAGE_HOME)

    def _make_nav(self, text: str, page: int) -> QPushButton:
        btn = QPushButton(text)
        btn.setCheckable(True)
        btn.clicked.connect(lambda: self._switch_page(page))
        self._nav_group.addButton(btn)
        return btn

    def _build_nowplaying(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("nowplaying")

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(8)

        # ── Left: track info ──
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        title = QLabel("Nothing playing")
        title.setObjectName("np-title")
        info_layout.addWidget(title)
        self._np_title = title

        artist = QLabel("—")
        artist.setObjectName("np-artist")
        info_layout.addWidget(artist)
        self._np_artist = artist

        layout.addLayout(info_layout, 3)

        # ── Center: controls + progress ──
        center = QVBoxLayout()
        center.setSpacing(2)

        controls = QHBoxLayout()
        controls.setAlignment(Qt.AlignmentFlag.AlignCenter)
        controls.setSpacing(4)

        btn_shuffle = QPushButton("\U0001f500")
        btn_shuffle.setObjectName("btn-shuffle")
        btn_shuffle.setProperty("active", False)
        btn_shuffle.clicked.connect(self._on_shuffle)
        controls.addWidget(btn_shuffle)
        self._btn_shuffle = btn_shuffle

        btn_prev = QPushButton("⏮")
        btn_prev.clicked.connect(self._on_prev)
        controls.addWidget(btn_prev)
        self._btn_prev = btn_prev

        btn_play = QPushButton("▶")
        btn_play.setObjectName("btn-play")
        btn_play.clicked.connect(lambda: self._player.toggle_pause())
        controls.addWidget(btn_play)
        self._btn_play = btn_play

        btn_next = QPushButton("⏭")
        btn_next.clicked.connect(self._on_next)
        controls.addWidget(btn_next)
        self._btn_next = btn_next

        btn_loop = QPushButton("\U0001f501")
        btn_loop.setObjectName("btn-loop")
        btn_loop.setProperty("active", False)
        btn_loop.clicked.connect(self._on_loop)
        controls.addWidget(btn_loop)
        self._btn_loop = btn_loop

        controls_widget = QWidget()
        controls_widget.setObjectName("np-controls")
        controls_widget.setLayout(controls)
        center.addWidget(controls_widget)

        # Progress row
        prog_row = QHBoxLayout()
        prog_row.setSpacing(8)

        cur_time = QLabel("0:00")
        cur_time.setObjectName("prog-cur")
        prog_row.addWidget(cur_time)
        self._prog_cur = cur_time

        prog_slider = QSlider(Qt.Orientation.Horizontal)
        prog_slider.setRange(0, 1000)
        prog_slider.sliderPressed.connect(self._on_seek_press)
        prog_slider.sliderReleased.connect(self._on_seek_release)
        prog_row.addWidget(prog_slider, 1)
        self._prog_slider = prog_slider

        end_time = QLabel("0:00")
        end_time.setObjectName("prog-end")
        prog_row.addWidget(end_time)
        self._prog_end = end_time

        center.addLayout(prog_row)
        layout.addLayout(center, 4)

        # ── Right: volume ──
        vol_layout = QHBoxLayout()
        vol_layout.setAlignment(Qt.AlignmentFlag.AlignRight)
        vol_layout.setSpacing(4)

        vol_icon = QLabel("\U0001f50a")
        vol_icon.setObjectName("vol-icon")
        vol_layout.addWidget(vol_icon)

        vol_slider = QSlider(Qt.Orientation.Horizontal)
        vol_slider.setObjectName("vol-slider")
        vol_slider.setRange(0, 100)
        vol_slider.setValue(100)
        vol_slider.valueChanged.connect(self._on_volume_change)
        vol_layout.addWidget(vol_slider)
        self._vol_slider = vol_slider

        layout.addLayout(vol_layout, 2)

        return bar

    # ── Signal connections ──

    def _connect_signals(self) -> None:
        self._player.state_changed.connect(self._on_state_changed)
        self._player.position_changed.connect(self._on_position_changed)

    def _on_state_changed(self, state: PlaybackState) -> None:
        self._np_title.setText(state.title)
        self._np_artist.setText(f"•  {state.artist}" if state.artist != "—" else "")

        icon = "⏸" if state.status == PlaybackStatus.PLAYING else "▶"
        self._btn_play.setText(icon)

        self._vol_slider.blockSignals(True)
        self._vol_slider.setValue(state.volume)
        self._vol_slider.blockSignals(False)

    def _on_position_changed(self, time_pos: float, duration: float) -> None:
        if self._seeking:
            return
        self._prog_cur.setText(_fmt_time(time_pos))
        self._prog_end.setText(_fmt_time(duration))
        if duration > 0:
            self._prog_slider.blockSignals(True)
            self._prog_slider.setValue(int(time_pos / duration * 1000))
            self._prog_slider.blockSignals(False)

    # ── Navigation ──

    def _switch_page(self, page: int) -> None:
        self._current_page = page
        self._stack.setCurrentIndex(page)
        if page < len(self._nav_buttons):
            self._nav_buttons[page].setChecked(True)

        # Hide now-playing shuffle/loop on non-music pages
        on_music = page == PAGE_MUSIC
        self._btn_shuffle.setVisible(on_music)
        self._btn_loop.setVisible(on_music)

        # Focus search on music/video pages
        if page == PAGE_MUSIC:
            self._music.focus_search()
        elif page == PAGE_VIDEO:
            self._video.focus_search()

    def _on_home_navigate(self, target: str) -> None:
        if target == "video":
            self._switch_page(PAGE_VIDEO)
        elif target == "music":
            self._switch_page(PAGE_MUSIC)

    # ── Control handlers ──

    def _on_shuffle(self) -> None:
        self._music._toggle_shuffle()
        active = self._music._shuffle_on
        self._btn_shuffle.setProperty("active", active)
        self._btn_shuffle.style().unpolish(self._btn_shuffle)
        self._btn_shuffle.style().polish(self._btn_shuffle)

    def _on_loop(self) -> None:
        self._music._toggle_loop()
        active = self._music._loop_on
        self._btn_loop.setProperty("active", active)
        self._btn_loop.style().unpolish(self._btn_loop)
        self._btn_loop.style().polish(self._btn_loop)

    def _on_prev(self) -> None:
        if self._current_page == PAGE_MUSIC:
            self._music._play_prev()
        elif self._current_page == PAGE_VIDEO:
            self._player.seek(-10)

    def _on_next(self) -> None:
        if self._current_page == PAGE_MUSIC:
            self._music._play_next()
        elif self._current_page == PAGE_VIDEO:
            self._player.seek(10)

    def _on_volume_change(self, vol: int) -> None:
        self._player.set_volume(vol)

    def _on_seek_press(self) -> None:
        self._seeking = True

    def _on_seek_release(self) -> None:
        self._seeking = False
        state = self._player.state
        if state.duration > 0:
            pos = self._prog_slider.value() / 1000.0 * state.duration
            delta = pos - state.time_pos
            self._player.seek(delta)

    # ── Keyboard shortcuts ──

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence(Qt.Key.Key_Space), self, lambda: self._player.toggle_pause())
        QShortcut(QKeySequence(Qt.Key.Key_Left), self, self._on_kb_seek_back)
        QShortcut(QKeySequence(Qt.Key.Key_Right), self, self._on_kb_seek_fwd)
        QShortcut(QKeySequence(Qt.Key.Key_Up), self, self._on_kb_vol_up)
        QShortcut(QKeySequence(Qt.Key.Key_Down), self, self._on_kb_vol_down)
        QShortcut(QKeySequence(Qt.Key.Key_Equal), self, self._on_kb_vol_up)
        QShortcut(QKeySequence(Qt.Key.Key_Minus), self, self._on_kb_vol_down)
        QShortcut(QKeySequence(Qt.Key.Key_Return), self, self._on_kb_enter)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, self._on_kb_esc)

    def _on_kb_seek_back(self) -> None:
        delta = -5 if self._current_page == PAGE_MUSIC else -10
        self._player.seek(delta)

    def _on_kb_seek_fwd(self) -> None:
        delta = 5 if self._current_page == PAGE_MUSIC else 10
        self._player.seek(delta)

    def _on_kb_vol_up(self) -> None:
        self._player.set_volume(self._player.state.volume + 5)

    def _on_kb_vol_down(self) -> None:
        self._player.set_volume(self._player.state.volume - 5)

    def _on_kb_enter(self) -> None:
        if self._current_page == PAGE_MUSIC:
            self._music._play_selected()
        elif self._current_page == PAGE_VIDEO:
            self._video._play_selected()

    def _on_kb_esc(self) -> None:
        if self._current_page != PAGE_HOME:
            self._switch_page(PAGE_HOME)

    # ── Cleanup ──

    def closeEvent(self, event) -> None:
        self._player.cleanup_sync()
        super().closeEvent(event)
