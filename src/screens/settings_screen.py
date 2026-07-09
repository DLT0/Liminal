"""Settings screen — app configuration."""

from __future__ import annotations

import asyncio

from textual.screen import Screen
from textual.widgets import Static, Button
from textual.containers import Vertical, Horizontal

from src.config import MUSIC_DIR, VIDEO_DIR


class SettingsScreen(Screen):

    def compose(self):
        with Vertical(id="wrapper"):
            yield Static("⚙  S E T T I N G S", id="title")
            yield Static(f"\nMusic folder: {MUSIC_DIR}", id="setting-music")
            yield Static(f"Video folder: {VIDEO_DIR}", id="setting-video")
            yield Static("\n[Keys]", id="keys-header")
            yield Static("↑/↓  Navigate tracks")
            yield Static("Enter  Play selected")
            yield Static("Space  Toggle pause")
            yield Static("←/→   Seek ±5s")
            yield Static("+/−   Volume")
            yield Static("Tab   Focus search")
            yield Static("Esc   Back")
            yield Static("\n[Info]", id="info-header")
            yield Static("Liminal v0.1 — Local Media Player")
            yield Static("Backend: mpv via JSON IPC")

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss()
