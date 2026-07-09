# src/screens/main_screen.py
import os
from textual.screen import Screen
from textual.widgets import Button, Static
from textual.containers import Vertical

class MainScreen(Screen):
    # Trỏ ra ngoài tìm thư mục css/main.css dựa vào vị trí app.py chạy
    CSS_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../CSS/main.css"))

    def compose(self):
        with Vertical(id="wrapper"):
            yield Static("L I M I N A L", id="title")
            yield Static("LOCAL MEDIA PLAYER", id="tagline")
            yield Button("📺  Video", id="video")
            yield Button("🎵  Music", id="music")
            yield Static("q quit  ·  ? help", id="footer")
