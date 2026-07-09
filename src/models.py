# src/models.py
from dataclasses import dataclass

@dataclass
class Track:
    title: str
    artist: str
    duration: str
    track_num: str = "1"
    is_playing: bool = False
