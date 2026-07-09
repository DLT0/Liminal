# src/player.py
class LiminalPlayer:
    def __init__(self):
        self.current_media = None

    def play(self, media_path: str):
        # Sau này tích hợp vlc/mpv ở đây
        self.current_media = media_path
        print(f"Playing: {media_path}")

    def pause(self):
        print("Media paused")
