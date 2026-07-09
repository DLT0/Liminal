"""Liminal — Local Media Player (Textual TUI)."""

from textual.app import App
from textual.widgets import Button

from src.player import LiminalPlayer
from src.screens.main_screen import MainScreen
from src.screens.music_screen import MusicScreen
from src.screens.video_screen import VideoScreen


class LiminalApp(App):
    TITLE = "Liminal"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.player = LiminalPlayer()

    def on_mount(self) -> None:
        self.push_screen(MainScreen())

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "video":
            self.push_screen(VideoScreen(self.player))
        elif event.button.id == "music":
            self.push_screen(MusicScreen(self.player))

    def on_key(self, event) -> None:
        if event.key == "q":
            self.exit()

    def _on_exit(self) -> None:
        self.player.cleanup_sync()


if __name__ == "__main__":
    LiminalApp().run()
