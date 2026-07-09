# src/screens/video_screen.py
import os
from textual.screen import Screen
from textual.widgets import Static

class VideoScreen(Screen):
    CSS_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../CSS/video.css"))

    def compose(self):
        yield Static("📺 VIDEO SCREEN — COMING SOON\n\n[Press ESC or Q to Go Back]", id="video-msg")

    def on_key(self, event) -> None:
        if event.key == "escape" or event.key == "q":
            self.dismiss()
