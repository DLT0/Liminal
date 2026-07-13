"""MPV video player for Focus Mode.

X11/xcb: embed via --wid into a native host widget.
Wayland: borderless mpv window synced to the QML video area via --geometry.
Falls back to Qt Multimedia only when mpv is not installed.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import subprocess
from enum import Enum
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QObject, QPointF, QTimer, Qt, pyqtProperty, pyqtSignal, pyqtSlot
from PyQt6.QtQuick import QQuickItem
from PyQt6.QtWidgets import QWidget

from src.config import mpv_audio_gain_args
from src.player import mpv_end_reason_is_eof

logger = logging.getLogger(__name__)

_RUNTIME_DIR = os.environ.get("XDG_RUNTIME_DIR", f"/tmp/liminal-{os.getuid()}")
os.makedirs(_RUNTIME_DIR, exist_ok=True)
IPC_SOCKET = os.path.join(_RUNTIME_DIR, f"mpv-video-{os.getpid()}.sock")

# High-quality decode + upscale/downscale.  gpu-next is used when available.
_MPV_QUALITY_ARGS = (
    "--hwdec=auto-safe",
    "--vo=gpu-next,gpu",
    "--gpu-context=auto",
    "--profile=gpu-hq",
    "--scale=ewa_lanczossharp",
    "--dscale=ewa_lanczossharp",
    "--cscale=ewa_lanczossharp",
    "--deband=yes",
    "--video-sync=display-resample",
    "--interpolation",
)


class _PlaybackMode(str, Enum):
    NONE = "none"
    WID = "wid"
    GEOMETRY = "geometry"


def _mpv_executable() -> str | None:
    return shutil.which(os.environ.get("LIMINAL_MPV", "mpv"))


def _detect_playback_mode() -> _PlaybackMode:
    if not _mpv_executable():
        return _PlaybackMode.NONE
    platform = os.environ.get("QT_QPA_PLATFORM", "").lower()
    if platform.startswith("wayland"):
        return _PlaybackMode.GEOMETRY
    if os.environ.get("DISPLAY"):
        return _PlaybackMode.WID
    if os.environ.get("WAYLAND_DISPLAY"):
        return _PlaybackMode.GEOMETRY
    return _PlaybackMode.NONE


class _VideoHostWidget(QWidget):
    """Native window surface passed to mpv via --wid."""

    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.BypassWindowManagerHint
            | Qt.WindowType.Tool,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DontCreateNativeAncestors, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setStyleSheet("background: black;")


class MpvVideoBridge(QObject):
    """Qt bridge for mpv video playback in Focus Mode."""

    availableChanged = pyqtSignal()
    playingChanged = pyqtSignal()
    positionChanged = pyqtSignal(int)
    durationChanged = pyqtSignal(int)
    mediaEnded = pyqtSignal()
    errorOccurred = pyqtSignal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._process: Optional[subprocess.Popen] = None
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._listener_task: Optional[asyncio.Task] = None
        self._pending: dict[str, asyncio.Future] = {}
        self._req_id = 0
        self._host: Optional[_VideoHostWidget] = None
        self._anchor: Optional[QQuickItem] = None
        self._main_window = None
        self._playing = False
        self._position_ms = 0
        self._duration_ms = 0
        self._volume = 100
        self._muted = False
        self._source = ""
        self._mode = _detect_playback_mode()
        self._last_geometry = ""

        self._geom_timer = QTimer(self)
        self._geom_timer.setInterval(33)
        self._geom_timer.timeout.connect(self._sync_geometry)

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(400)
        self._poll_timer.timeout.connect(self._poll_state)

    @pyqtProperty(bool, notify=availableChanged)
    def available(self) -> bool:
        return self._mode is not _PlaybackMode.NONE

    @pyqtProperty(bool, constant=True)
    def geometryMode(self) -> bool:
        return self._mode is _PlaybackMode.GEOMETRY

    @pyqtProperty(bool, notify=playingChanged)
    def playing(self) -> bool:
        return self._playing

    @pyqtProperty(int, notify=positionChanged)
    def position(self) -> int:
        return self._position_ms

    @pyqtProperty(int, notify=durationChanged)
    def duration(self) -> int:
        return self._duration_ms

    @pyqtSlot(QObject)
    def setMainWindow(self, window: QObject) -> None:
        self._main_window = window

    @pyqtSlot(QQuickItem)
    def attachToItem(self, item: QQuickItem) -> None:
        if not self.available:
            return
        self._anchor = item
        if self._mode is _PlaybackMode.WID and self._host is None:
            self._host = _VideoHostWidget()
            self._host.winId()
        self._geom_timer.start()
        self._sync_geometry()

    @pyqtSlot()
    def detach(self) -> None:
        self._geom_timer.stop()
        self._poll_timer.stop()
        asyncio.ensure_future(self._stop_mpv())
        if self._host is not None:
            self._host.hide()
        self._anchor = None
        self._last_geometry = ""

    @pyqtSlot(str)
    def play(self, source: str) -> None:
        if not self.available or not source:
            return
        self._source = source
        asyncio.ensure_future(self._play_async(source))

    @pyqtSlot()
    def pause(self) -> None:
        asyncio.ensure_future(self._set_pause(True))

    @pyqtSlot()
    def resume(self) -> None:
        asyncio.ensure_future(self._set_pause(False))

    @pyqtSlot()
    def togglePause(self) -> None:
        asyncio.ensure_future(self._send_command(["cycle", "pause"]))

    @pyqtSlot(int)
    def seek(self, position_ms: int) -> None:
        asyncio.ensure_future(
            self._send_command(["seek", max(0.0, position_ms / 1000.0), "absolute"])
        )

    @pyqtSlot(int)
    def setVolume(self, percent: int) -> None:
        self._volume = max(0, min(100, percent))
        asyncio.ensure_future(self._send_command(["set_property", "volume", self._volume]))

    @pyqtSlot(bool)
    def setMuted(self, muted: bool) -> None:
        self._muted = muted
        asyncio.ensure_future(self._send_command(["set_property", "mute", muted]))

    @pyqtSlot()
    def stop(self) -> None:
        asyncio.ensure_future(self._stop_mpv())

    def cleanup_sync(self) -> None:
        self._geom_timer.stop()
        self._poll_timer.stop()
        if self._process:
            try:
                self._process.terminate()
                self._process.wait(2)
            except Exception:
                try:
                    self._process.kill()
                except Exception:
                    pass
            self._process = None
        Path(IPC_SOCKET).unlink(missing_ok=True)
        if self._host is not None:
            self._host.close()
            self._host = None

    def _current_geometry(self) -> str | None:
        if self._anchor is None or not self._anchor.isVisible():
            return None
        top_left = self._anchor.mapToGlobal(QPointF(0, 0))
        width = max(1, int(self._anchor.width()))
        height = max(1, int(self._anchor.height()))
        return f"{width}x{height}+{int(top_left.x())}+{int(top_left.y())}"

    def _sync_geometry(self) -> None:
        if self._anchor is None:
            return
        geometry = self._current_geometry()
        if geometry is None:
            if self._host is not None:
                self._host.hide()
            return

        if self._mode is _PlaybackMode.WID and self._host is not None:
            parts = geometry.split("+", 1)
            size = parts[0].split("x")
            pos = parts[1].split("+") if len(parts) > 1 else ["0", "0"]
            self._host.setGeometry(int(pos[0]), int(pos[1]), int(size[0]), int(size[1]))
            self._host.show()

        if self._main_window is not None:
            self._main_window.raise_()

        if (
            self._mode is _PlaybackMode.GEOMETRY
            and self._writer is not None
            and geometry != self._last_geometry
        ):
            self._last_geometry = geometry
            asyncio.ensure_future(self._send_command(["set_property", "geometry", geometry]))

    async def _play_async(self, source: str) -> None:
        geometry = self._current_geometry()
        if geometry is None:
            return
        self._sync_geometry()

        path = source
        if not path.startswith(("http://", "https://", "file://")):
            path = str(Path(path).expanduser().resolve())

        can_reuse = (
            self._writer is not None
            and self._process is not None
            and self._process.poll() is None
        )
        if can_reuse:
            await self._send_command(["loadfile", path, "replace"])
            await self._send_command(["set_property", "pause", False])
            self._set_playing(True)
            return

        await self._stop_mpv()
        Path(IPC_SOCKET).unlink(missing_ok=True)

        cmd = [
            _mpv_executable() or "mpv",
            f"--input-ipc-server={IPC_SOCKET}",
            *_MPV_QUALITY_ARGS,
            "--keep-open=no",
            "--no-terminal",
            "--msg-level=all=no",
            *mpv_audio_gain_args(),
            f"--volume={self._volume}",
        ]
        if self._muted:
            cmd.append("--mute=yes")

        if self._mode is _PlaybackMode.WID:
            if self._host is None:
                return
            cmd.append(f"--wid={int(self._host.winId())}")
        else:
            cmd.extend([
                f"--geometry={geometry}",
                "--no-border",
                "--force-window=immediate",
                "--focus-on-open=no",
            ])

        cmd.append(path)

        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self._last_geometry = geometry
        if not await self._connect_ipc():
            self.errorOccurred.emit("Không thể kết nối mpv để phát video.")
            return

        await self._send_command(["observe_property", 1, "pause"])
        await self._send_command(["observe_property", 2, "time-pos"])
        await self._send_command(["observe_property", 3, "duration"])
        self._set_playing(True)
        self._poll_timer.start()
        if self._main_window is not None:
            self._main_window.raise_()

    async def _stop_mpv(self) -> None:
        if self._listener_task:
            self._listener_task.cancel()
            self._listener_task = None
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
            self._writer = None
            self._reader = None
        if self._process:
            try:
                self._process.terminate()
                await asyncio.to_thread(self._process.wait, 2)
            except Exception:
                try:
                    self._process.kill()
                except Exception:
                    pass
            self._process = None
        Path(IPC_SOCKET).unlink(missing_ok=True)
        self._set_playing(False)
        self._position_ms = 0
        self._duration_ms = 0
        self.positionChanged.emit(0)
        self.durationChanged.emit(0)

    async def _set_pause(self, paused: bool) -> None:
        if self._writer:
            await self._send_command(["set_property", "pause", paused])
            self._set_playing(not paused)

    def _set_playing(self, playing: bool) -> None:
        if self._playing != playing:
            self._playing = playing
            self.playingChanged.emit()

    def _poll_state(self) -> None:
        if self._process is not None and self._process.poll() is not None:
            self._on_mpv_disconnected()

    def _on_mpv_disconnected(self) -> None:
        self._process = None
        self._set_playing(False)

    async def _connect_ipc(self) -> bool:
        sock_path = Path(IPC_SOCKET)
        for _ in range(40):
            if sock_path.exists():
                try:
                    self._reader, self._writer = await asyncio.open_unix_connection(str(sock_path))
                    self._listener_task = asyncio.create_task(self._listen())
                    return True
                except Exception:
                    await asyncio.sleep(0.05)
                    continue
            await asyncio.sleep(0.05)
        return False

    async def _listen(self) -> None:
        buf = ""
        try:
            while self._writer and not self._writer.is_closing():
                data = await self._reader.read(4096)
                if not data:
                    break
                buf += data.decode("utf-8")
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        await self._dispatch(json.loads(line))
                    except json.JSONDecodeError:
                        logger.warning("bad json from mpv video: %s", line)
        except asyncio.CancelledError:
            pass
        except Exception:
            pass
        finally:
            self._writer = None
            self._reader = None
            self._listener_task = None
            self._on_mpv_disconnected()

    async def _dispatch(self, msg: dict) -> None:
        rid = msg.get("request_id")
        if rid is not None:
            fut = self._pending.pop(str(rid), None)
            if fut and not fut.done():
                fut.set_result(msg)
        if "event" not in msg:
            return
        ev = msg["event"]
        if ev == "end-file":
            reason = msg.get("reason", 0)
            self._set_playing(False)
            if mpv_end_reason_is_eof(reason):
                self.mediaEnded.emit()
        elif ev == "property-change":
            name = msg.get("name")
            data = msg.get("data")
            if name == "pause":
                self._set_playing(not bool(data))
            elif name == "time-pos":
                ms = int((data or 0) * 1000)
                if ms != self._position_ms:
                    self._position_ms = ms
                    self.positionChanged.emit(ms)
            elif name == "duration":
                ms = int((data or 0) * 1000)
                if ms != self._duration_ms:
                    self._duration_ms = ms
                    self.durationChanged.emit(ms)

    async def _send_command(self, cmd: list) -> dict:
        if not self._writer:
            return {"error": "not connected"}
        self._req_id += 1
        payload = {"command": cmd, "request_id": self._req_id}
        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[str(self._req_id)] = fut
        try:
            self._writer.write((json.dumps(payload) + "\n").encode())
            await self._writer.drain()
            return await asyncio.wait_for(fut, timeout=5.0)
        except asyncio.TimeoutError:
            self._pending.pop(str(self._req_id), None)
            return {"error": "timeout"}
        except Exception:
            self._pending.pop(str(self._req_id), None)
            return {"error": "disconnected"}
