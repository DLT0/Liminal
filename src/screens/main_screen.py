"""Main menu screen with navigation buttons."""

from textual.screen import Screen
from textual.widgets import Button, Static
from textual.containers import Vertical

from src.config import CSS_DIR


class MainScreen(Screen):
    CSS_PATH = str(CSS_DIR / "main.css")

    def compose(self):
        with Vertical(id="wrapper"):
            yield Static("L I M I N A L", id="title")
            yield Static("LOCAL MEDIA PLAYER", id="tagline")
            yield Button("📺  Video", id="video")
            yield Button("🎵  Music", id="music")
            yield Static("q quit  ·  esc back", id="footer")
