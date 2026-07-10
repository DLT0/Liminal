"""Intro Splash Screen for PyQt6 — Fixed 600x600px centered viewport with zoomed video using QGraphicsView for native clipping."""

from __future__ import annotations

import os

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QRectF, QSizeF, QTimer, QUrl, Qt, pyqtSignal
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtMultimediaWidgets import QGraphicsVideoItem
from PyQt6.QtWidgets import QApplication, QFrame, QGraphicsScene, QGraphicsView, QWidget


class IntroSplash(QWidget):
    """
    Fixed 600x600px centered splash screen.
    Uses QGraphicsView + QGraphicsScene + QGraphicsVideoItem to force robust CPU/GPU
    clipping to the 600x600 boundaries, bypassing QVideoWidget's native surface issues.
    Zoomed by 1.75x (175%) to crop corner watermarks/logos (like Gemini).
    Emits `finished` signal when playback and transition complete.
    """

    finished = pyqtSignal()

    def __init__(self, video_path: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.video_path = os.path.normpath(video_path)
        self._fading = False

        # 1. Setup Window Flags for a premium frameless splash overlay
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.SubWindow
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        # 2. Fix the geometry of the widget window to exactly 600x600px
        self.setFixedSize(600, 600)
        self._center_on_screen()

        # 3. Setup QGraphicsScene (Defines the 600x600 coordinate boundary)
        self.scene = QGraphicsScene(self)
        self.scene.setSceneRect(QRectF(0, 0, 600, 600))

        # 4. Setup QGraphicsView (Layer 1: Visual viewport & Clipping Container)
        # QGraphicsView acts as the viewport frame. It strictly crops/clips everything
        # outside its 600x600 layout space using the Graphics Framework clipping path.
        self.view = QGraphicsView(self.scene, self)
        self.view.setGeometry(0, 0, 600, 600)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setFrameShape(QFrame.Shape.NoFrame)
        # Apply dark background (#0B1020) and premium rounded corners
        self.view.setStyleSheet("background: #0B1020; border-radius: 35px;")

        # 5. Setup QGraphicsVideoItem (Layer 2: Zoomed video item inside Scene)
        # To zoom the 16:9 video to 1.15x (115%) and crop out corner watermarks:
        # Base cover height = 600, Base width = 600 * 16 / 9 = 1067
        # Zoomed height = 600 * 1.15 = 690, Zoomed width = 1067 * 1.15 = 1227
        # Center inside 600x600 scene: x = (600 - 1227) // 2 = -313, y = (600 - 690) // 2 = -45
        self.video_item = QGraphicsVideoItem()
        self.video_item.setSize(QSizeF(1227, 690))
        self.video_item.setPos(-313, -45)
        self.video_item.setAspectRatioMode(Qt.AspectRatioMode.IgnoreAspectRatio)
        self.scene.addItem(self.video_item)

        # 6. Setup QMediaPlayer & Audio Output
        self.media_player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.audio_output.setVolume(1.0)
        self.media_player.setAudioOutput(self.audio_output)
        # Set video output to our QGraphicsVideoItem instead of QVideoWidget
        self.media_player.setVideoOutput(self.video_item)

        # 7. Bind Player signals to manage transitions and catch errors
        self.media_player.mediaStatusChanged.connect(self._on_media_status_changed)
        self.media_player.playbackStateChanged.connect(self._on_playback_state_changed)
        self.media_player.errorOccurred.connect(self._on_player_error)

        # 8. Setup smooth transition: QPropertyAnimation for fade out
        self.fade_animation = QPropertyAnimation(self, b"windowOpacity")
        self.fade_animation.setDuration(600)  # 600ms fade transition
        self.fade_animation.setStartValue(1.0)
        self.fade_animation.setEndValue(0.0)
        self.fade_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.fade_animation.finished.connect(self._on_fade_finished)

        # 9. Setup fallback safety timer (5.0s maximum load/play budget)
        self.safety_timer = QTimer(self)
        self.safety_timer.setSingleShot(True)
        self.safety_timer.timeout.connect(self._on_safety_timeout)

        # 10. Setup play duration timer (exactly 2.835s / 2835ms)
        self.duration_timer = QTimer(self)
        self.duration_timer.setSingleShot(True)
        self.duration_timer.timeout.connect(self._start_fade_out)

    def _center_on_screen(self) -> None:
        """Move the fixed-size splash widget to the center of the active screen."""
        screen = QApplication.primaryScreen()
        if screen:
            geom = screen.geometry()
            x = (geom.width() - self.width()) // 2
            y = (geom.height() - self.height()) // 2
            self.move(x, y)

    def start(self) -> None:
        """Start loading and playing the intro. Falls back if video file doesn't exist."""
        if not os.path.isfile(self.video_path):
            print(f"[IntroSplash] Video file not found: {self.video_path}")
            self._trigger_fallback()
            return

        self.media_player.setSource(QUrl.fromLocalFile(self.video_path))
        self.show()
        self.raise_()
        self.safety_timer.start(5000)  # 5 seconds maximum budget

    def _on_media_status_changed(self, status: QMediaPlayer.MediaStatus) -> None:
        """Signal listener to start playback once media has successfully loaded."""
        if status == QMediaPlayer.MediaStatus.LoadedMedia:
            self.safety_timer.stop()
            self.media_player.play()
            # Start the 2.835s countdown
            self.duration_timer.start(2835)
        elif status == QMediaPlayer.MediaStatus.InvalidMedia:
            print("[IntroSplash] Error loading video: invalid format or codec.")
            self._trigger_fallback()

    def _on_playback_state_changed(self, state: QMediaPlayer.PlaybackState) -> None:
        """Signal listener to trigger fade out once video finishes playing."""
        if state == QMediaPlayer.PlaybackState.StoppedState and not self._fading:
            self.duration_timer.stop()
            self._start_fade_out()

    def _on_player_error(self, error: QMediaPlayer.Error, error_string: str) -> None:
        """Gracefully handle playback/load errors and enter the app directly."""
        print(f"[IntroSplash] Playback error: {error_string}")
        self._trigger_fallback()

    def _on_safety_timeout(self) -> None:
        """Fallback safety triggered if media loading stalls/hangs."""
        print("[IntroSplash] Safety timeout reached before loading/playback finished.")
        self._trigger_fallback()

    def _trigger_fallback(self) -> None:
        """Abort intro animation and transition immediately to the main screen."""
        self.safety_timer.stop()
        self.duration_timer.stop()
        self.media_player.stop()
        self.close()
        self.finished.emit()

    def _start_fade_out(self) -> None:
        """Start animating window opacity to 0."""
        self.duration_timer.stop()
        self._fading = True
        self.fade_animation.start()

    def _on_fade_finished(self) -> None:
        """Clean up media player resources and notify parent once fade-out completes."""
        self.media_player.stop()
        self.close()
        self.finished.emit()
