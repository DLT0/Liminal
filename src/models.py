"""Data models for Liminal."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


class PlaybackStatus(Enum):
    STOPPED = auto()
    PLAYING = auto()
    PAUSED = auto()


@dataclass
class MediaInfo:
    """Represents a media file or search result."""

    path: str
    title: str
    artist: str = "Unknown Artist"
    duration: str = "--:--"
    num: str = "1"
    url: str = ""  # download URL (set for search results)


@dataclass
class PlaybackState:
    """Live state from the mpv backend."""

    status: PlaybackStatus = PlaybackStatus.STOPPED
    path: Optional[str] = None
    title: str = "Nothing playing"
    artist: str = "—"
    time_pos: float = 0.0
    duration: float = 0.0
    volume: int = 100
    paused: bool = False
