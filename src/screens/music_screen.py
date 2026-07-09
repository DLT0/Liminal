# src/screens/music_screen.py
import os
from textual.screen import Screen
from textual.widgets import Static, Input
from textual.containers import Vertical, Horizontal

class MusicScreen(Screen):
    CSS_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../CSS/music.css"))

    def compose(self):
        with Vertical():
            with Horizontal(id="topbar"):
                yield Input(placeholder="search tracks, artists...", id="search-input")

            with Horizontal(id="main-body"):
                with Vertical(id="sidebar"):
                    yield Static("▶ Library", classes="nav-item active")
                    yield Static("  Playlists", classes="nav-item")
                    yield Static("  Settings", classes="nav-item")

                with Vertical(id="content"):
                    yield Static("ALL TRACKS — 4 songs", id="content-header")
                    with Vertical(id="track-list"):
                        with Horizontal(classes="track playing"):
                            yield Static("▶", classes="track-num pi")
                            with Vertical(classes="track-info"):
                                yield Static("Walpurgis", classes="track-title playing")
                                yield Static("Mili", classes="track-artist")
                            yield Static("3:42", classes="track-dur")
                        
                        with Horizontal(classes="track"):
                            yield Static("2", classes="track-num")
                            with Vertical(classes="track-info"):
                                yield Static("Mirror", classes="track-title")
                                yield Static("Unknown Artist", classes="track-artist")
                            yield Static("4:11", classes="track-dur")

                        with Horizontal(classes="track"):
                            yield Static("3", classes="track-num")
                            with Vertical(classes="track-info"):
                                yield Static("Inauthenticity", classes="track-title")
                                yield Static("Mili", classes="track-artist")
                            yield Static("2:58", classes="track-dur")

                        with Horizontal(classes="track"):
                            yield Static("4", classes="track-num")
                            with Vertical(classes="track-info"):
                                yield Static("Ashes", classes="track-title")
                                yield Static("Unknown Artist", classes="track-artist")
                            yield Static("5:03", classes="track-dur")

            with Horizontal(id="nowplaying"):
                with Vertical(id="np-left"):
                    yield Static("Walpurgis", id="np-title")
                    yield Static("Mili", id="np-artist")

                with Vertical(id="np-center"):
                    yield Static("🔀  ⏮  ⏸  ⏭  🔁", id="np-controls")
                    with Horizontal(id="np-progress-container"):
                        yield Static("1:18", classes="prog-time")
                        yield Static("███████░░░░░░░░░░░░░░░░░░░░░░", id="prog-bar-mock")
                        yield Static("3:42", classes="prog-time")

                with Horizontal(id="np-right"):
                    yield Static("🔊 ███████░░░", id="vol-mock")

    def on_key(self, event) -> None:
        if event.key == "escape" or event.key == "q":
            self.dismiss()
