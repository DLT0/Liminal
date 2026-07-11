"""MPV-based media player controlled via JSON IPC.

Spawns mpv as a subprocess with a Unix socket for bidirectional control.
Exposes async methods for play/pause/seek/volume and emits playback state
updates via polling so the TUI can render them.

PlayerBridge is a QObject wrapper that emits Qt signals for use in PyQt6 GUI.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Callable, Optional

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from src.models import PlaybackState, PlaybackStatus

logger = logging.getLogger(__name__)

# Each Liminal process needs its own mpv IPC socket.  A shared path lets one
# app instance unlink another instance's socket, leaving its PlayerBar unable
# to pause, seek, mute, or change volume.
IPC_SOCKET = f"/tmp/liminal-mpv-{os.getpid()}.sock"


class LiminalPlayer:
    """Async controller for an mpv subprocess via JSON IPC."""

    def __init__(self) -> None:
        self._process: Optional[subprocess.Popen] = None
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._listener_task: Optional[asyncio.Task] = None
        self._poll_task: Optional[asyncio.Task] = None
        self._pending: dict[str, asyncio.Future] = {}
        self._req_id: int = 0
        self.state: PlaybackState = PlaybackState()
        self._mpv_available: bool = self._check_mpv()
        self._on_end_file: Optional[Callable[[], None]] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def available(self) -> bool:
        return self._mpv_available

    async def play(
        self,
        path: str,
        audio_only: bool = False,
        title: str = "",
        artist: str = "",
    ) -> None:
        """Start playing a media file or stream URL.

        Args:
            path: Path to the media file or streaming URL.
            audio_only: If True, no video window opens (for music).
            title: Optional display title (used for remote streams).
            artist: Optional display artist (used for remote streams).
        """
        if not self._mpv_available:
            self.state.title = "mpv not installed — install with: sudo pacman -S mpv"
            self.state.status = PlaybackStatus.STOPPED
            return

        await self.stop()

        # Clean up stale socket from a previous crash
        stale = Path(IPC_SOCKET)
        stale.unlink(missing_ok=True)

        window_flag = "--no-video" if audio_only else "--force-window=yes"

        cmd = [
            "mpv",
            f"--input-ipc-server={IPC_SOCKET}",
            "--keep-open=yes",
            window_flag,
            "--no-terminal",
            "--msg-level=all=no",
            f"--volume={self.state.volume}",
            path,
        ]
        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        connected = await self._connect_ipc()
        if not connected:
            self.state.title = "Failed to connect to mpv"
            return

        # Subscribe to property changes
        await self._send_command(["observe_property", 1, "pause"])
        await self._send_command(["observe_property", 2, "time-pos"])
        await self._send_command(["observe_property", 3, "duration"])
        await self._send_command(["observe_property", 4, "volume"])

        p = Path(path)
        self.state.path = path
        if title:
            self.state.title = title[:40]
        elif path.startswith(("http://", "https://")):
            self.state.title = "Streaming"
        else:
            self.state.title = p.stem
        self.state.artist = artist if artist else "—"
        self.state.status = PlaybackStatus.PLAYING
        self.state.paused = False

        # Start a background poller for time-pos (events may throttle)
        self._poll_task = asyncio.create_task(self._poll_time_pos())

    async def toggle_pause(self) -> None:
        if self._writer and self.state.status != PlaybackStatus.STOPPED:
            await self._send_command(["cycle", "pause"])

    async def seek(self, delta: float) -> None:
        if self._writer and self.state.status != PlaybackStatus.STOPPED:
            await self._send_command(["seek", delta, "relative"])

    async def seek_absolute(self, position: float) -> None:
        if self._writer and self.state.status != PlaybackStatus.STOPPED:
            await self._send_command(["seek", max(0.0, position), "absolute"])

    async def set_volume(self, vol: int) -> None:
        vol = max(0, min(100, vol))
        self.state.volume = vol
        if self._writer:
            await self._send_command(["set", "volume", vol])

    async def stop(self) -> None:
        """Kill mpv and reset state."""
        # Cancel background tasks
        if self._poll_task:
            self._poll_task.cancel()
            self._poll_task = None
        if self._listener_task:
            self._listener_task.cancel()
            self._listener_task = None

        # Close IPC connection
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
            self._writer = None
            self._reader = None

        # Terminate process
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

        stale = Path(IPC_SOCKET)
        stale.unlink(missing_ok=True)
        self.state = PlaybackState()

    def cleanup_sync(self) -> None:
        """Synchronous cleanup for app exit (called from non-async contexts)."""
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
        stale = Path(IPC_SOCKET)
        stale.unlink(missing_ok=True)

    # ------------------------------------------------------------------
    # IPC internals
    # ------------------------------------------------------------------

    def _check_mpv(self) -> bool:
        try:
            subprocess.run(
                ["mpv", "--version"],
                capture_output=True,
                timeout=5,
            )
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    async def _connect_ipc(self) -> bool:
        sock_path = Path(IPC_SOCKET)
        for _ in range(20):  # Wait up to 2 s
            if sock_path.exists():
                try:
                    self._reader, self._writer = await asyncio.open_unix_connection(
                        str(sock_path)
                    )
                    self._listener_task = asyncio.create_task(self._listen())
                    return True
                except Exception:
                    await asyncio.sleep(0.1)
                    continue
            await asyncio.sleep(0.1)
        return False

    async def _listen(self) -> None:
        """Continuously read JSON messages from mpv."""
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
                        logger.warning("bad json from mpv: %s", line)
        except (ConnectionError, asyncio.CancelledError):
            pass
        finally:
            self._writer = None
            self._reader = None

    async def _dispatch(self, msg: dict) -> None:
        rid = msg.get("request_id")
        if rid is not None:
            fut = self._pending.pop(str(rid), None)
            if fut and not fut.done():
                fut.set_result(msg)
        if "event" in msg:
            ev = msg["event"]
            if ev == "end-file":
                self.state.status = PlaybackStatus.STOPPED
                self.state.time_pos = 0.0
                if self._on_end_file:
                    self._on_end_file()
            elif ev == "property-change":
                name = msg.get("name")
                data = msg.get("data")
                if name == "pause":
                    self.state.paused = bool(data)
                    self.state.status = (
                        PlaybackStatus.PAUSED if data else PlaybackStatus.PLAYING
                    )
                elif name == "time-pos":
                    self.state.time_pos = data if data is not None else 0.0
                elif name == "duration":
                    self.state.duration = data if data is not None else 0.0
                elif name == "volume":
                    self.state.volume = data if data is not None else 100

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

    async def _poll_time_pos(self) -> None:
        """Poll time-pos and duration every ~500ms since mpv event throttling can be loose."""
        try:
            while self._writer and not self._writer.is_closing():
                if self.state.status == PlaybackStatus.PLAYING:
                    resp = await self._send_command(["get_property", "time-pos"])
                    if resp.get("data") is not None and resp.get("error") == "success":
                        self.state.time_pos = resp["data"]
                    dur = await self._send_command(["get_property", "duration"])
                    if dur.get("data") is not None and dur.get("error") == "success":
                        self.state.duration = dur["data"]
                await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            pass


class PlayerBridge(QObject):
    """Qt signal bridge wrapping LiminalPlayer for PyQt6 GUI use.

    Emits signals on state changes so the UI can react without polling.
    Public methods schedule async calls on the event loop.
    """

    state_changed = pyqtSignal(PlaybackState)
    position_changed = pyqtSignal(float, float)  # time_pos, duration
    track_ended = pyqtSignal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._player = LiminalPlayer()
        self._prev_state: Optional[PlaybackState] = None

        self._timer = QTimer(self)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self._poll)
        self._timer.start()

        self._player._on_end_file = self._on_track_end

    @property
    def state(self) -> PlaybackState:
        return self._player.state

    @property
    def available(self) -> bool:
        return self._player.available

    def play(
        self,
        path: str,
        audio_only: bool = False,
        title: str = "",
        artist: str = "",
    ) -> None:
        asyncio.ensure_future(
            self._player.play(path, audio_only, title=title, artist=artist)
        )

    def toggle_pause(self) -> None:
        asyncio.ensure_future(self._player.toggle_pause())

    def seek(self, delta: float) -> None:
        asyncio.ensure_future(self._player.seek(delta))

    def seek_absolute(self, position: float) -> None:
        asyncio.ensure_future(self._player.seek_absolute(position))

    def set_volume(self, vol: int) -> None:
        asyncio.ensure_future(self._player.set_volume(vol))

    def stop(self) -> None:
        asyncio.ensure_future(self._player.stop())

    def cleanup_sync(self) -> None:
        self._timer.stop()
        self._player.cleanup_sync()

    def _poll(self) -> None:
        """Emit signals if state has changed since last poll."""
        s = self._player.state
        prev = self._prev_state

        if prev is not None:
            if s.time_pos != prev.time_pos or s.duration != prev.duration:
                self.position_changed.emit(s.time_pos, s.duration)

        if prev is None or self._state_different(s, prev):
            self.state_changed.emit(s)

        self._prev_state = PlaybackState(
            status=s.status,
            path=s.path,
            title=s.title,
            artist=s.artist,
            time_pos=s.time_pos,
            duration=s.duration,
            volume=s.volume,
            paused=s.paused,
        )

    def _on_track_end(self) -> None:
        self.track_ended.emit()

    @staticmethod
    def _state_different(a: PlaybackState, b: PlaybackState) -> bool:
        return (
            a.status != b.status
            or a.title != b.title
            or a.artist != b.artist
            or a.volume != b.volume
            or a.paused != b.paused
            or a.path != b.path
        )
