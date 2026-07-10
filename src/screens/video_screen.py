"""Video browser — browse, filter, and play local video files."""

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
from src.scanner import scan_video


def _fmt_time(seconds: float) -> str:
    if seconds <= 0:
        return "0:00"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


class VideoScreen(Screen):
    CSS_PATH = str(CSS_DIR / "video.css")

    def __init__(self, player: LiminalPlayer, **kwargs) -> None:
        super().__init__(**kwargs)
        self._player = player
        self._all_videos = scan_video()
        self._video_widgets: list[Horizontal] = []
        self._filtered_indices: list[int] = list(range(len(self._all_videos)))
        self._selected_index: int = 0
        self._refresh_task: Optional[asyncio.Task] = None

    async def on_mount(self) -> None:
        container = self.query_one("#content-list", Vertical)
        header = self.query_one("#content-header", Static)
        header.update(f"VIDEO LIBRARY — {len(self._all_videos)} file{'s' if len(self._all_videos) != 1 else ''}")

        widgets = []
        for i, v in enumerate(self._all_videos):
            row = Horizontal(
                Static(v.num, classes="vid-num"),
                Static(v.title, classes="vid-title"),
                Static(v.duration, classes="vid-dur"),
                classes="video-row",
                id=f"vr-{i}",
            )
            widgets.append(row)
            self._video_widgets.append(row)

        if widgets:
            await container.mount(*widgets)
        self._highlight_selection()

        # Keep input focused for typing
        self.call_after_refresh(lambda: self._focus_input())

        self._refresh_task = asyncio.create_task(self._refresh_loop())

    def _focus_input(self) -> None:
        try:
            self.set_focus(self.query_one("#search-input", Input))
        except Exception:
            pass

    def on_unmount(self) -> None:
        if self._refresh_task:
            self._refresh_task.cancel()

    def compose(self):
        with Vertical():
            with Horizontal(id="topbar"):
                yield Input(placeholder="filter videos...", id="search-input")

            with Horizontal(id="main-body"):
                with Vertical(id="content"):
                    yield Static(id="content-header")
                    with Vertical(id="content-list"):
                        pass

            with Horizontal(id="nowplaying"):
                with Vertical(id="np-info"):
                    yield Static(self._player.state.title, id="np-title")
                    yield Static(self._player.state.artist, id="np-artist")
                with Vertical(id="np-center"):
                    with Horizontal(id="np-controls"):
                        yield Static("⏮", id="btn-prev", classes="ctrl-btn")
                        yield Static("⏸", id="btn-play", classes="ctrl-btn")
                        yield Static("⏭", id="btn-next", classes="ctrl-btn")
                    with Horizontal(id="np-progress"):
                        yield Static("0:00", classes="prog-time", id="prog-cur")
                        yield Static("░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░", id="prog-bar")
                        yield Static("0:00", classes="prog-time", id="prog-end")
                with Horizontal(id="np-volume"):
                    yield Static("🔊", id="vol-icon")
                    yield Static("██████░", id="vol-bar")

    # ── Filter ──

    def on_input_submitted(self, event: Input.Submitted) -> None:
        query = event.value.strip().lower()
        self._filtered_indices = []
        for i, v in enumerate(self._all_videos):
            match = (not query) or query in v.title.lower()
            self._video_widgets[i].display = match
            if match:
                self._filtered_indices.append(i)
        self._selected_index = 0
        n = len(self._filtered_indices)
        self.query_one("#content-header", Static).update(
            f"VIDEO LIBRARY — {n} file{'s' if n != 1 else ''}"
        )
        self._highlight_selection()

    # ── Selection ──

    def _real_index(self) -> int:
        if not self._filtered_indices:
            return -1
        idx = self._selected_index
        if idx < 0 or idx >= len(self._filtered_indices):
            return -1
        return self._filtered_indices[idx]

    def _highlight_selection(self) -> None:
        for node in self.query(".video-row.selected"):
            node.remove_class("selected")
        real = self._real_index()
        if real < 0:
            return
        self._video_widgets[real].add_class("selected")
        self._video_widgets[real].scroll_visible()

    # ── Now-playing ──

    def _update_now_playing(self) -> None:
        s = self._player.state
        q = self.query_one
        q("#np-title", Static).update(s.title)
        q("#np-artist", Static).update(s.artist)

        q("#btn-play", Static).update("⏸" if s.status == PlaybackStatus.PLAYING else "▶")

        avail = self.size.width - 28
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

        blocks = max(1, min(6, int(s.volume / 17))) if s.volume > 0 else 0
        q("#vol-bar", Static).update("█" * blocks + "░" * (6 - blocks))

    async def _refresh_loop(self) -> None:
        try:
            while True:
                self._update_now_playing()
                await asyncio.sleep(0.25)
        except asyncio.CancelledError:
            pass

    # ── Key / click ──

    def on_static_pressed(self, event: Static.Pressed) -> None:
        sid = event.static.id
        if sid == "btn-play":
            asyncio.create_task(self._player.toggle_pause())
        elif sid == "btn-prev":
            asyncio.create_task(self._player.seek(-10))
        elif sid == "btn-next":
            asyncio.create_task(self._player.seek(10))

    def on_key(self, event) -> None:
        inp = self.query_one("#search-input", Input)
        if self.focused is inp:
            if event.key in ("up", "down"):
                if event.key == "up":
                    self._selected_index = max(0, self._selected_index - 1)
                else:
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
                asyncio.create_task(self._player.play(self._all_videos[real].path))
        elif event.key == "space":
            asyncio.create_task(self._player.toggle_pause())
        elif event.key == "left":
            asyncio.create_task(self._player.seek(-10))
        elif event.key == "right":
            asyncio.create_task(self._player.seek(10))
        elif event.key in ("+", "="):
            asyncio.create_task(self._player.set_volume(self._player.state.volume + 5))
        elif event.key == "-":
            asyncio.create_task(self._player.set_volume(self._player.state.volume - 5))
