"""Home / welcome widget for Liminal."""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget


class HomeWidget(QWidget):
    navigate = pyqtSignal(str)  # "video" or "music"

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(12)

        title = QLabel("L I M I N A L")
        title.setObjectName("home-title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        tagline = QLabel("LOCAL MEDIA PLAYER")
        tagline.setObjectName("home-tagline")
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)

        btn_video = QPushButton("\U0001f4fa  Video")
        btn_video.setObjectName("home-btn-video")
        btn_video.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_video.clicked.connect(lambda: self.navigate.emit("video"))

        btn_music = QPushButton("\U0001f3b5  Music")
        btn_music.setObjectName("home-btn-music")
        btn_music.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_music.clicked.connect(lambda: self.navigate.emit("music"))

        footer = QLabel("q quit  ·  esc back  ·  space pause  ·  ←→ seek")
        footer.setObjectName("home-footer")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addStretch()
        layout.addWidget(title)
        layout.addWidget(tagline)
        layout.addSpacing(16)
        layout.addWidget(btn_video, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(btn_music, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(footer, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addStretch()

        self.setLayout(layout)
