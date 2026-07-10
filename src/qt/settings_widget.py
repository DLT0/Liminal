"""Settings widget."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from src.config import MUSIC_DIR, VIDEO_DIR


class SettingsWidget(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout()
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(8)

        title = QLabel("⚙  S E T T I N G S")
        title.setObjectName("settings-title")
        layout.addWidget(title)

        # Paths
        paths_label = QLabel("[Paths]")
        paths_label.setObjectName("settings-section")
        layout.addWidget(paths_label)

        music = QLabel(f"Music folder: {MUSIC_DIR}")
        music.setObjectName("settings-value")
        layout.addWidget(music)

        video = QLabel(f"Video folder: {VIDEO_DIR}")
        video.setObjectName("settings-value")
        layout.addWidget(video)

        # Keys
        keys_label = QLabel("[Keys]")
        keys_label.setObjectName("settings-section")
        layout.addWidget(keys_label)

        shortcuts = [
            "↑/↓  Navigate tracks",
            "Enter  Play selected",
            "Space  Toggle pause",
            "←/→  Seek ±5s / ±10s",
            "+/−  Volume",
            "Esc  Back",
        ]
        for s in shortcuts:
            lbl = QLabel(s)
            lbl.setObjectName("settings-value")
            layout.addWidget(lbl)

        # Info
        info_label = QLabel("[Info]")
        info_label.setObjectName("settings-section")
        layout.addWidget(info_label)

        info = QLabel("Liminal v0.2 — Local Media Player\nBackend: mpv via JSON IPC  |  UI: PyQt6")
        info.setObjectName("settings-value")
        layout.addWidget(info)

        layout.addStretch()
        self.setLayout(layout)
