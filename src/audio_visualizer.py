"""Real-time audio visualizer using PipeWire monitor source.

Captures audio from the default sink's monitor (the audio already sent to
speakers) via sounddevice, computes a log-frequency FFT, and emits
levelsChanged(list[float]) at ~40 ms intervals so QML can render equalizer
bars without polling.

Graceful degradation
---------------------
If no .monitor source is found (non-standard PipeWire config, missing pactl,
etc.) the instance sets ``available = False``, logs a warning, and never
starts the capture thread.  The QML component should render flat/idle bars
whenever ``available`` is False.

Thread safety
-------------
The capture loop runs in a ``threading.Thread``.  The signal ``levelsChanged``
is connected with Qt.QueuedConnection by default (cross-thread), so QML
updates always happen on the main thread.
"""

from __future__ import annotations

import logging
import subprocess
import threading
import time
from typing import Optional

import os
import numpy as np
from PyQt6.QtCore import QObject, pyqtProperty, pyqtSignal

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

_SAMPLE_RATE = 44100          # Hz — request from sounddevice
_BLOCK_FRAMES = 2048          # samples per capture block (~46 ms) - higher resolution for bass
_NUM_BANDS = 24               # equalizer bar count
_EMIT_INTERVAL = 0.04         # seconds between levelsChanged emits (~25 fps)
_SMOOTH_ALPHA = 0.40          # EMA coefficient (higher = faster response to transients)
_DB_FLOOR = -55.0             # dB level treated as silence (higher = more sensitive)
_DB_CEIL = 0.0                # dB level treated as full amplitude (maps to 1.0)

# Log-frequency bin edges — 20 Hz … 20 000 Hz split into _NUM_BANDS bands
_FREQ_MIN = 20.0
_FREQ_MAX = 20_000.0


def _log_band_edges(n_bands: int, sr: int) -> list[int]:
    """Return FFT bin indices for log-frequency band boundaries."""
    nyquist = sr / 2.0
    edges = np.logspace(
        np.log10(_FREQ_MIN),
        np.log10(min(_FREQ_MAX, nyquist)),
        n_bands + 1,
    )
    fft_size = _BLOCK_FRAMES // 2 + 1
    bin_edges = np.round(edges / nyquist * (fft_size - 1)).astype(int)
    bin_edges = np.clip(bin_edges, 0, fft_size - 1)
    return bin_edges.tolist()


class AudioVisualizer(QObject):
    """Captures live audio from PipeWire and emits FFT band levels.

    Usage::

        viz = AudioVisualizer()
        engine.rootContext().setContextProperty("audioVisualizer", viz)

        # Connect lifecycle to PlayerBridge signals
        player.state_changed.connect(viz.on_player_state_changed)
        app.aboutToQuit.connect(viz.stop)

    QML binds to ``audioVisualizer.levelsChanged`` and
    ``audioVisualizer.available``.
    """

    # Emits list of float in [0.0, 1.0], length == numBands
    levelsChanged = pyqtSignal("QVariantList")
    availableChanged = pyqtSignal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

        self._monitor_device: Optional[str] = None
        self._available: bool = False
        self._running: bool = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Pre-compute band edges once
        self._band_edges: list[int] = _log_band_edges(_NUM_BANDS, _SAMPLE_RATE)
        # EMA state — start silent
        self._smoothed = np.zeros(_NUM_BANDS, dtype=np.float32)
        # Throttle tracking
        self._last_emit: float = 0.0

        # Detect monitor source at construction time (fast subprocess call)
        self._monitor_device = self._detect_monitor_source()
        self._available = self._monitor_device is not None

        if self._available:
            logger.info(
                "AudioVisualizer: found monitor source %r", self._monitor_device
            )
        else:
            logger.warning(
                "AudioVisualizer: no PipeWire/PulseAudio monitor source found. "
                "Equalizer visualizer will be disabled."
            )

    # ── Public Qt properties ───────────────────────────────────────────────

    @pyqtProperty(bool, notify=availableChanged)
    def available(self) -> bool:
        """True if a monitor source was detected and capture is possible."""
        return self._available

    @pyqtProperty(int, constant=True)
    def numBands(self) -> int:
        """Number of FFT frequency bands emitted per levelsChanged signal."""
        return _NUM_BANDS

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the audio capture thread.  No-op if not available or already running."""
        if not self._available:
            return
        with self._lock:
            if self._running:
                return
            self._running = True
        self._thread = threading.Thread(
            target=self._capture_loop,
            name="AudioVisualizerCapture",
            daemon=True,
        )
        self._thread.start()
        logger.debug("AudioVisualizer: capture thread started")

    def stop(self) -> None:
        """Stop the capture thread gracefully."""
        with self._lock:
            self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        # Emit flat state so QML bars drop to zero
        self._smoothed[:] = 0.0
        self.levelsChanged.emit([0.0] * _NUM_BANDS)
        logger.debug("AudioVisualizer: capture thread stopped")

    def on_player_state_changed(self, state) -> None:  # noqa: ANN001
        """Slot to connect with PlayerBridge.state_changed.

        Automatically starts/stops capture based on playback state.
        Expects a PlaybackState-like object with ``.paused`` and ``.status``.
        """
        from src.models import PlaybackStatus  # avoid circular at module level

        is_active = (
            state.status == PlaybackStatus.PLAYING
            and not state.paused
        )
        if is_active:
            self.start()
        else:
            self.stop()

    # ── Internal capture loop ──────────────────────────────────────────────

    def _capture_loop(self) -> None:
        """Main loop: open sounddevice InputStream and process blocks."""
        try:
            import sounddevice as sd  # imported here so app still runs without it
        except (ImportError, OSError) as exc:
            logger.error(
                "AudioVisualizer: sounddevice/PortAudio not available (%s). "
                "Install portaudio: sudo dnf install portaudio",
                exc,
            )
            if self._available:
                self._available = False
                self.availableChanged.emit()
            return

        try:
            # Route ALSA default device to the monitor node using PipeWire/Pulse environment variables
            if self._monitor_device:
                os.environ["PULSE_SOURCE"] = self._monitor_device
                os.environ["PIPEWIRE_NODE"] = self._monitor_device

            with sd.InputStream(
                device=None,  # Use default input (which ALSA wraps and env var redirects)
                channels=2,
                samplerate=_SAMPLE_RATE,
                blocksize=_BLOCK_FRAMES,
                dtype="float32",
            ) as stream:
                logger.debug(
                    "AudioVisualizer: stream opened via default device redirected to %r",
                    self._monitor_device,
                )
                while True:
                    with self._lock:
                        if not self._running:
                            break
                    audio_block, _overflowed = stream.read(_BLOCK_FRAMES)
                    self._process_block(audio_block)

        except Exception as exc:
            logger.error("AudioVisualizer: stream error — %s", exc)
            self._available = False
            self.availableChanged.emit()

    def _process_block(self, block: "np.ndarray") -> None:
        """Compute FFT, map to log bands, smooth, and emit at throttled rate."""
        # Mix down to mono
        mono = block.mean(axis=1) if block.ndim == 2 else block.ravel()

        # Apply Hann window to reduce spectral leakage
        window = np.hanning(len(mono))
        windowed = mono * window

        # Compute magnitude spectrum (positive half)
        spectrum = np.abs(np.fft.rfft(windowed))

        # Map to log-frequency bands
        bands = np.zeros(_NUM_BANDS, dtype=np.float32)
        edges = self._band_edges
        for i in range(_NUM_BANDS):
            lo = edges[i]
            hi = max(edges[i + 1], lo + 1)
            segment = spectrum[lo:hi]
            bands[i] = float(segment.mean()) if len(segment) > 0 else 0.0

        # Convert to dB, normalise to [0, 1]
        with np.errstate(divide="ignore"):
            db = 20.0 * np.log10(np.maximum(bands, 1e-10))
        normalised = np.clip(
            (db - _DB_FLOOR) / (_DB_CEIL - _DB_FLOOR), 0.0, 1.0
        ).astype(np.float32)

        # Apply a custom frequency weighting profile optimized for EDM/remix music
        # First 6 bands (bass/low-end): boost progressively up to 1.5x. Mids: boost slightly.
        boost = np.ones(_NUM_BANDS, dtype=np.float32)
        for idx in range(6):
            boost[idx] = 1.5 - (idx * 0.08)  # 1.5x down to 1.1x
        for idx in range(6, 12):
            boost[idx] = 1.1 - ((idx - 6) * 0.02)  # 1.1x down to 1.0x
        normalised = np.clip(normalised * boost, 0.0, 1.0)

        # Exponential moving average smoothing
        self._smoothed = (
            _SMOOTH_ALPHA * normalised + (1.0 - _SMOOTH_ALPHA) * self._smoothed
        )

        # Throttle emits so we don't spam QML
        now = time.monotonic()
        if now - self._last_emit >= _EMIT_INTERVAL:
            self._last_emit = now
            levels = [round(float(v), 4) for v in self._smoothed]
            # Signal is queued across thread boundary automatically by Qt
            self.levelsChanged.emit(levels)

    # ── PipeWire / PulseAudio monitor detection ────────────────────────────

    @staticmethod
    def _detect_monitor_source() -> Optional[str]:
        """Return the sounddevice input device name for the default sink monitor.

        Strategy:
        1. Ask ``pactl list sources short`` for sources ending in ``.monitor``.
        2. Prefer the one matching the default sink (``pactl info``).
        3. Fall back to any ``.monitor`` source.
        4. Return None if none found or pactl unavailable.
        """
        try:
            # --- get default sink name ---
            info_out = subprocess.run(
                ["pactl", "info"],
                capture_output=True, text=True, timeout=5
            )
            default_sink = ""
            for line in info_out.stdout.splitlines():
                if "Default Sink:" in line:
                    default_sink = line.split(":", 1)[1].strip()
                    break

            # --- list all monitor sources ---
            list_out = subprocess.run(
                ["pactl", "list", "sources", "short"],
                capture_output=True, text=True, timeout=5
            )
            monitors: list[str] = []
            for line in list_out.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 2:
                    name = parts[1]
                    if name.endswith(".monitor"):
                        monitors.append(name)

            if not monitors:
                logger.warning(
                    "AudioVisualizer: pactl found no .monitor sources"
                )
                return None

            # Prefer default sink monitor
            preferred = default_sink + ".monitor"
            if preferred in monitors:
                return preferred

            # Fall back to first available monitor
            return monitors[0]

        except FileNotFoundError:
            logger.warning(
                "AudioVisualizer: pactl not found — cannot detect monitor source"
            )
        except subprocess.TimeoutExpired:
            logger.warning(
                "AudioVisualizer: pactl timed out"
            )
        except Exception as exc:
            logger.warning(
                "AudioVisualizer: unexpected error detecting monitor source: %s", exc
            )
        return None
