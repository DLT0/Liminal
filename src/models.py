"""Data models for Liminal."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


class PlaybackStatus(Enum):
    STOPPED = auto()
    PLAYING = auto()
    PAUSED = auto()


class MediaKind(Enum):
    FILE = auto()
    ALBUM = auto()
    VIDEO_PLAYLIST = auto()
    FOLDER = auto()


@dataclass
class MediaInfo:
    """Represents a media file or search result."""

    path: str
    title: str
    artist: str = "Unknown Artist"
    duration: str = "--:--"
    num: str = "1"
    url: str = ""  # download URL (set for search results)
    track_id: str = ""  # stable id for remote items
    kind: MediaKind = MediaKind.FILE
    child_count: int = 0
    image: str = ""
    preview_images: list[str] = field(default_factory=list)
    canonical_path: str = ""  # resolved file path (for symlinked album entries)


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
