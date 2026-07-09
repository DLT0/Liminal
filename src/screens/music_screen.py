"""Music browser — browse, filter, and play local audio files."""

from __future__ import annotations

import asyncio
import math
from typing import Optional

from textual.screen import Screen
from textual.widgets import Static, Input
from textual.containers import Vertical, Horizontal

from src.config import CSS_DIR
from src.models import PlaybackStatus
from src.player import LiminalPlayer
from src.scanner import scan_music
from src.screens.playlist_screen import PlaylistScreen
from src.screens.settings_screen import SettingsScreen


def _fmt_time(seconds: float) -> str:
    if seconds <= 0:
        return "0:00"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


class MusicScreen(Screen):
    CSS_PATH = str(CSS_DIR / "music.css")

    def __init__(self, player: LiminalPlayer, **kwargs) -> None:
        super().__init__(**kwargs)
        self._player = player
        self._all_tracks = scan_music()
        self._track_widgets: list[Horizontal] = []
        self._filtered_indices: list[int] = list(range(len(self._all_tracks)))
        self._selected_index: int = 0
        self._shuffle_on: bool = False
        self._loop_on: bool = False
        self._played_history: list[int] = []  # for shuffle
        self._refresh_task: Optional[asyncio.Task] = None

    # ── Lifecycle ──────────────────────────────────────────────

    async def on_mount(self) -> None:
        # Build all track widgets ONCE
        container = self.query_one("#content-list", Vertical)
        header = self.query_one("#content-header", Static)
        header.update(f"ALL TRACKS — {len(self._all_tracks)} songs")

        widgets = []
        for i, t in enumerate(self._all_tracks):
            row = Horizontal(
                Static(t.num, classes="track-num"),
                Vertical(
                    Static(t.title, classes="track-title"),
                    Static(t.artist, classes="track-artist"),
                    classes="track-info",
                ),
                Static(t.duration, classes="track-dur"),
                classes="track",
                id=f"tr-{i}",
            )
            widgets.append(row)
            self._track_widgets.append(row)

        if widgets:
            await container.mount(*widgets)
        self._highlight_selection()

        # Register end-file callback for auto-next
        self._player._on_end_file = self._on_track_end

        # Defocus Input so keys go to screen first
        self.call_after_refresh(lambda: self.set_focus(None))

        self._refresh_task = asyncio.create_task(self._refresh_loop())

    def on_unmount(self) -> None:
        if self._refresh_task:
            self._refresh_task.cancel()
        self._player._on_end_file = None

    def compose(self):
        with Vertical():
            with Horizontal(id="topbar"):
                yield Input(placeholder="filter tracks...", id="search-input")

            with Horizontal(id="main-body"):
                with Vertical(id="sidebar"):
                    yield Static("▶ Library", classes="nav-item active", id="nav-library")
                    yield Static("  Playlists", classes="nav-item", id="nav-playlists")
                    yield Static("  Settings", classes="nav-item", id="nav-settings")

                with Vertical(id="content"):
                    yield Static(id="content-header")
                    with Vertical(id="content-list"):
                        pass

            # Now-playing bar — Spotify-style
            with Vertical(id="nowplaying"):
                with Horizontal(id="np-top"):
                    with Vertical(id="np-left"):
                        yield Static(self._player.state.title, id="np-title")
                        yield Static(self._player.state.artist, id="np-artist")
                    with Horizontal(id="np-controls"):
                        yield Static("🔀", id="btn-shuffle", classes="ctrl-btn")
                        yield Static("⏮", id="btn-prev", classes="ctrl-btn")
                        yield Static("⏸", id="btn-play", classes="ctrl-btn")
                        yield Static("⏭", id="btn-next", classes="ctrl-btn")
                        yield Static("🔁", id="btn-loop", classes="ctrl-btn")
                    with Horizontal(id="np-right"):
                        yield Static("", id="spacer-right")

                with Horizontal(id="np-bottom"):
                    yield Static("0:00", classes="prog-time", id="prog-cur")
                    yield Static("░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░", id="prog-bar")
                    yield Static("0:00", classes="prog-time", id="prog-end")
                    yield Static("🔊", id="vol-icon")
                    yield Static("██████░", id="vol-bar")

    # ── Filter ─────────────────────────────────────────────────

    def on_input_submitted(self, event: Input.Submitted) -> None:
        query = event.value.strip().lower()
        self._filtered_indices = []
        for i, t in enumerate(self._all_tracks):
            match = (not query) or query in t.title.lower() or query in t.artist.lower()
            self._track_widgets[i].display = match
            if match:
                self._filtered_indices.append(i)
        self._selected_index = 0
        n = len(self._filtered_indices)
        self.query_one("#content-header", Static).update(
            f"ALL TRACKS — {n} song{'s' if n != 1 else ''}"
        )
        self._highlight_selection()

    # ── Selection ──────────────────────────────────────────────

    def _real_index(self) -> int:
        if not self._filtered_indices:
            return -1
        idx = self._selected_index
        if idx < 0 or idx >= len(self._filtered_indices):
            return -1
        return self._filtered_indices[idx]

    def _highlight_selection(self) -> None:
        for node in self.query(".track.selected"):
            node.remove_class("selected")
        real = self._real_index()
        if real < 0:
            return
        w = self._track_widgets[real]
        w.add_class("selected")
        w.scroll_visible()

    # ── Auto‑next / shuffle ────────────────────────────────────

    def _on_track_end(self) -> None:
        """Called when mpv finishes playing a track."""
        asyncio.create_task(self._play_next())

    async def _play_next(self) -> None:
        if not self._filtered_indices:
            return
        n = len(self._filtered_indices)
        if self._shuffle_on:
            # Pick random, avoid immediate repeat
            import random
            candidates = [i for i in range(n) if i != self._selected_index]
            if candidates:
                self._selected_index = random.choice(candidates)
        else:
            self._selected_index = (self._selected_index + 1) % n
            if not self._loop_on and self._selected_index == 0:
                return  # stop at end

        self._highlight_selection()
        real = self._real_index()
        if real >= 0:
            await self._player.play(self._all_tracks[real].path, audio_only=True)

    async def _play_prev(self) -> None:
        if not self._filtered_indices:
            return
        n = len(self._filtered_indices)
        self._selected_index = (self._selected_index - 1) % n
        self._highlight_selection()
        real = self._real_index()
        if real >= 0:
            await self._player.play(self._all_tracks[real].path, audio_only=True)

    # ── Now‑playing ────────────────────────────────────────────

    def _update_now_playing(self) -> None:
        s = self._player.state
        q = self.query_one

        q("#np-title", Static).update(s.title)
        q("#np-artist", Static).update(s.artist)

        play_btn = q("#btn-play", Static)
        play_btn.update("⏸" if s.status == PlaybackStatus.PLAYING else "▶")

        # Shuffle / Loop highlight
        q("#btn-shuffle", Static).set_class(self._shuffle_on, "active")
        q("#btn-loop", Static).set_class(self._loop_on, "active")

        # Progress bar — dynamic width based on terminal
        avail = self.size.width - 32  # reserve for times + volume + margins
        bar_w = max(10, avail)

        q("#prog-cur", Static).update(_fmt_time(s.time_pos))
        q("#prog-end", Static).update(_fmt_time(s.duration))

        bar = q("#prog-bar", Static)
        if s.duration > 0:
            pct = min(s.time_pos / s.duration, 1.0)
            filled = int(pct * bar_w)
            bar.update("█" * filled + "░" * (bar_w - filled))
        else:
            bar.update("░" * bar_w)

        # Volume
        blocks = max(1, min(6, int(s.volume / 17))) if s.volume > 0 else 0
        q("#vol-bar", Static).update("█" * blocks + "░" * (6 - blocks))

    async def _refresh_loop(self) -> None:
        try:
            while True:
                self._update_now_playing()
                await asyncio.sleep(0.25)
        except asyncio.CancelledError:
            pass

    # ── Key / click handling ───────────────────────────────────

    def on_static_pressed(self, event: Static.Pressed) -> None:
        sid = event.static.id
        if sid == "btn-play":
            asyncio.create_task(self._player.toggle_pause())
        elif sid == "btn-prev":
            asyncio.create_task(self._play_prev())
        elif sid == "btn-next":
            asyncio.create_task(self._play_next())
        elif sid == "btn-shuffle":
            self._shuffle_on = not self._shuffle_on
        elif sid == "btn-loop":
            self._loop_on = not self._loop_on
        elif sid == "nav-playlists":
            self.app.push_screen(PlaylistScreen())
        elif sid == "nav-settings":
            self.app.push_screen(SettingsScreen())

    def on_key(self, event) -> None:
        inp = self.query_one("#search-input", Input)
        if self.focused is inp:
            if event.key == "up":
                self._selected_index = max(0, self._selected_index - 1)
                self._highlight_selection()
            elif event.key == "down":
                self._selected_index = min(len(self._filtered_indices) - 1, self._selected_index + 1)
                self._highlight_selection()
            elif event.key == "escape":
                self.set_focus(None)
            return

        if event.key == "escape":
            self.dismiss()
        elif event.key == "up":
            self._selected_index = max(0, self._selected_index - 1)
            self._highlight_selection()
        elif event.key == "down":
            self._selected_index = min(len(self._filtered_indices) - 1, self._selected_index + 1)
            self._highlight_selection()
        elif event.key == "enter":
            real = self._real_index()
            if real >= 0:
                asyncio.create_task(self._player.play(self._all_tracks[real].path, audio_only=True))
        elif event.key == "space":
            asyncio.create_task(self._player.toggle_pause())
        elif event.key == "left":
            asyncio.create_task(self._player.seek(-5))
        elif event.key == "right":
            asyncio.create_task(self._player.seek(5))
        elif event.key in ("+", "="):
            asyncio.create_task(self._player.set_volume(self._player.state.volume + 5))
        elif event.key == "-":
            asyncio.create_task(self._player.set_volume(self._player.state.volume - 5))
