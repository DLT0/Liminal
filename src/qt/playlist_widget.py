"""Playlist placeholder widget."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class PlaylistWidget(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("\U0001f3b5  P L A Y L I S T S")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #e8e8e8;")

        msg = QLabel("\nNo playlists yet.\n\nCreate one from the Music screen.")
        msg.setStyleSheet("color: #666; font-size: 14px;")

        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(title)
        layout.addWidget(msg)
        self.setLayout(layout)
