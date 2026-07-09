# app.py
import sys
import os

# Thêm thư mục hiện tại vào PATH hệ thống để nhận diện package src/ chính xác
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from textual.app import App
from textual.widgets import Button
from src.screens.main_screen import MainScreen
from src.screens.music_screen import MusicScreen
from src.screens.video_screen import VideoScreen

class LiminalApp(App):
    TITLE = "Liminal"

    def on_mount(self) -> None:
        # Đặt màn hình MainScreen làm màn hình mặc định khi khởi động ứng dụng
        self.push_screen(MainScreen())

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "video":
            self.push_screen(VideoScreen())
        elif event.button.id == "music":
            self.push_screen(MusicScreen())

    def on_key(self, event) -> None:
        # Nếu nhấn q ở màn hình chính (khi không còn màn hình con nào đè lên), app sẽ đóng
        if event.key == "q" and len(self.screen_stack) <= 2:
            self.exit()

if __name__ == "__main__":
    LiminalApp().run()
