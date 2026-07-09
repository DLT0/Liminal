"""Playlist screen — view and manage playlists."""

from textual.screen import Screen
from textual.widgets import Static
from textual.containers import Vertical


class PlaylistScreen(Screen):

    def compose(self):
        with Vertical(id="wrapper"):
            yield Static("🎵  P L A Y L I S T S", id="title")
            yield Static("\nNo playlists yet.\n\nCreate one from the Music screen.", id="msg")

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss()
