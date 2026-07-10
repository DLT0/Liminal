"""Video intro overlay for Liminal — plays app_intro.mp4 for the first 3.5 s."""

from __future__ import annotations

import os

from PyQt6.QtCore import QTimer, QUrl, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtWidgets import QWidget

# Absolute path to the bundled intro video
# Video lives alongside this module in src/qt/
_INTRO_VIDEO = os.path.normpath(os.path.join(os.path.dirname(__file__), "app_intro.mp4"))

# How long to show the intro (ms).  The video is cut off / faded at this point.
INTRO_DURATION_MS = 3340

# Fade-out duration (ms)
FADE_MS = 300


def intro_fast_mode() -> bool:
    """Always return False so the intro video plays every time the app is opened."""
    return False


class _OverlayWidget(QWidget):
    """Draws the fade-out overlay layer on top of the video player."""
    def __init__(self, parent: IntroWidget) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._intro = parent

    def paintEvent(self, event) -> None:  # noqa: N802
        if self._intro._fading and self._intro._opacity < 1.0:
            painter = QPainter(self)
            # Overlay = black with increasing opacity as video fades
            alpha = int((1.0 - self._intro._opacity) * 255)
            painter.fillRect(self.rect(), QColor(11, 16, 32, alpha))
            painter.end()


class IntroWidget(QWidget):
    """Full-window video intro overlay.  Emits ``finished`` when done."""

    finished = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAutoFillBackground(False)

        self._opacity: float = 1.0          # used during fade-out (0.0 → 1.0 is visible)
        self._fade_step: float = 0.0        # increment per tick
        self._fading: bool = False

        # ── Video container (matches app window size for clipping) ────────────
        self._video_container = QWidget(self)
        self._video_container.setStyleSheet("background: #0B1020;")

        # ── Video player (Child of container, zoomed to crop corners) ──────────
        self._video_widget = QVideoWidget(self._video_container)
        self._video_widget.setStyleSheet("background: #0B1020;")
        self._video_widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        # Allow precise manual geometry-based scaling and centering
        self._video_widget.setAspectRatioMode(Qt.AspectRatioMode.IgnoreAspectRatio)

        # ── Overlay on top of Video ───────────────────────────────────────────
        self._overlay = _OverlayWidget(self)

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._player = QMediaPlayer(self)
        self._audio = QAudioOutput(self)
        self._audio.setVolume(1.0)
        self._player.setAudioOutput(self._audio)
        self._player.setVideoOutput(self._video_widget)

        # ── Timers ────────────────────────────────────────────────────────────
        # Hard cut-off timer (fires after INTRO_DURATION_MS)
        self._cutoff_timer = QTimer(self)
        self._cutoff_timer.setSingleShot(True)
        self._cutoff_timer.timeout.connect(self._begin_fade)

        # Fade-out tick (16 ms ≈ 60 fps)
        self._fade_timer = QTimer(self)
        self._fade_timer.setInterval(16)
        self._fade_timer.timeout.connect(self._fade_tick)

        # Also listen for natural end-of-video and errors
        self._player.playbackStateChanged.connect(self._on_playback_state)
        self._player.errorOccurred.connect(self._on_player_error)

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self, *, fast: bool = False) -> None:
        """Start playing the intro video.  If *fast* is True the intro is skipped."""
        if fast:
            # Skip immediately on repeat launches
            self._finish()
            return

        video_path = _INTRO_VIDEO
        if not os.path.isfile(video_path):
            # Gracefully skip if the video file is missing
            self._finish()
            return

        self._opacity = 1.0
        self._fading = False
        self.show()
        self.raise_()
        self.setFocus()

        self._player.setSource(QUrl.fromLocalFile(video_path))
        self._player.play()

        # Schedule hard cut-off
        self._cutoff_timer.start(INTRO_DURATION_MS)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _on_playback_state(self, state: QMediaPlayer.PlaybackState) -> None:
        """If the video ends before the timer, begin fade immediately."""
        if state == QMediaPlayer.PlaybackState.StoppedState and not self._fading:
            self._begin_fade()

    def _on_player_error(self, error: QMediaPlayer.Error, error_string: str) -> None:
        print(f"Intro Video Player Error ({error}): {error_string}")

    def _begin_fade(self) -> None:
        """Start the fade-out animation."""
        self._cutoff_timer.stop()
        if self._fading:
            return
        self._fading = True
        # Calculate decrement per 16 ms tick to reach 0 in FADE_MS
        steps = max(1, FADE_MS // 16)
        self._fade_step = 1.0 / steps
        self._fade_timer.start()

    def _fade_tick(self) -> None:
        self._opacity -= self._fade_step
        if self._opacity <= 0.0:
            self._opacity = 0.0
            self._fade_timer.stop()
            self._finish()
        else:
            self._overlay.update()   # trigger paintEvent on overlay

    def _finish(self) -> None:
        self.hide()
        self._player.stop()
        self._cutoff_timer.stop()
        self._fade_timer.stop()
        self.finished.emit()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        w = self.width()
        h = self.height()

        # Synchronize video container geometry to match the app window size exactly
        self._video_container.setGeometry(0, 0, w, h)

        # Video aspect ratio is 16:9 (1.7778)
        video_ratio = 16.0 / 9.0
        window_ratio = w / h if h > 0 else 1.0

        if window_ratio > video_ratio:
            # Window is wider than 16:9, width limits the cover size
            fw = w
            fh = w / video_ratio
        else:
            # Window is taller than 16:9, height limits the cover size
            fh = h
            fw = h * video_ratio

        # Scale to 175% to zoom in and crop out corners (Gemini logo)
        zw = int(fw * 1.75)
        zh = int(fh * 1.75)

        # Center the video widget inside the container
        zx = (w - zw) // 2
        zy = (h - zh) // 2

        self._video_widget.setGeometry(zx, zy, zw, zh)
        # Overlay matches parent size to cover the entire view
        self._overlay.setGeometry(0, 0, w, h)
        self._overlay.raise_()

    def paintEvent(self, event) -> None:  # noqa: N802
        # Draw dark backdrop color (#0B1020) over the entire window
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(11, 16, 32))
        painter.end()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self._begin_fade()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        self._begin_fade()
