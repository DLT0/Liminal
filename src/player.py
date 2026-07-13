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
import shutil
import subprocess
from pathlib import Path
from typing import Callable, Optional

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from src.config import mpv_audio_gain_args
from src.models import PlaybackState, PlaybackStatus

logger = logging.getLogger(__name__)

# Each Liminal process needs its own mpv IPC socket.  A shared path lets one
# app instance unlink another instance's socket, leaving its PlayerBar unable
# to pause, seek, mute, or change volume.
_RUNTIME_DIR = os.environ.get("XDG_RUNTIME_DIR", f"/tmp/liminal-{os.getuid()}")
os.makedirs(_RUNTIME_DIR, exist_ok=True)
IPC_SOCKET = os.path.join(_RUNTIME_DIR, f"mpv-{os.getpid()}.sock")

# mpv end-file reasons (see mpv manual: END_FILE_REASON_*)
_END_FILE_EOF = 0
_END_FILE_ERROR = 1
_END_FILE_QUIT = 2
_END_FILE_STOP = 4


def _mpv_executable() -> str | None:
    """Resolve mpv once through PATH, including distro/Flatpak wrappers."""
    return shutil.which(os.environ.get("LIMINAL_MPV", "mpv"))


class LiminalPlayer:
    """Async controller for the audio-only mpv subprocess via JSON IPC."""

    def __init__(self) -> None:
        self._process: Optional[subprocess.Popen] = None
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._listener_task: Optional[asyncio.Task] = None
        self._pending: dict[str, asyncio.Future] = {}
        self._req_id: int = 0
        self.state: PlaybackState = PlaybackState()
        self._mpv_available: bool = self._check_mpv()
        self._on_end_file: Optional[Callable[[], None]] = None
        self._properties_observed: bool = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def available(self) -> bool:
        return self._mpv_available

    async def play(
        self,
        path: str,
        title: str = "",
        artist: str = "",
        *,
        volume: int | None = None,
        muted: bool = False,
        start_pos: float = 0.0,
    ) -> None:
        """Start audio playback for a media file or stream URL.

        Args:
            path: Path to the media file or streaming URL.
            title: Optional display title (used for remote streams).
            artist: Optional display artist (used for remote streams).
            volume: Optional output volume (0-100) for this session.
            muted: Whether mpv should start muted while keeping volume level.
            start_pos: Start playback at this position in seconds.
        """
        if not self._mpv_available:
            from src.distro_detect import distro_package_manager
            self.state.title = f"mpv not installed — install with: {distro_package_manager()}"
            self.state.status = PlaybackStatus.STOPPED
            return

        if volume is not None:
            self.state.volume = max(0, min(100, volume))

        saved_volume = self.state.volume
        is_remote = path.startswith(("http://", "https://"))
        media_title = title or (
            "Streaming" if is_remote else Path(path).stem
        )

        can_reuse = (
            self._writer is not None
            and self._process is not None
            and self._process.poll() is None
            and self._properties_observed
        )
        if can_reuse:
            await self._play_via_loadfile(
                path,
                title=title,
                artist=artist,
                media_title=media_title,
                muted=muted,
                start_pos=start_pos,
            )
            return

        await self.stop()
        self.state.volume = saved_volume

        # Clean up stale socket from a previous crash
        stale = Path(IPC_SOCKET)
        stale.unlink(missing_ok=True)

        cmd = [
            _mpv_executable() or "mpv",
            f"--input-ipc-server={IPC_SOCKET}",
            "--keep-open=no",
            "--no-video",
            "--no-terminal",
            "--msg-level=all=no",
            *mpv_audio_gain_args(),
            f"--volume={saved_volume}",
            f"--force-media-title={media_title}",
        ]
        if is_remote:
            cmd.extend(["--cache=yes", "--demuxer-readahead-secs=10"])
        else:
            cmd.extend(["--cache=no", "--demuxer-readahead-secs=1"])
        if start_pos > 0.0:
            cmd.append(f"--start={start_pos}")
        cmd.append(path)

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
        self._properties_observed = True
        if muted:
            await self._send_command(["set_property", "mute", True])
        if artist or title:
            await self._send_command(
                [
                    "set_property",
                    "metadata",
                    {"Artist": artist or "—", "Title": media_title},
                ]
            )

        self._apply_play_state(path, title=title, artist=artist, media_title=media_title)

    async def _play_via_loadfile(
        self,
        path: str,
        *,
        title: str,
        artist: str,
        media_title: str,
        muted: bool,
        start_pos: float,
    ) -> None:
        load_cmd: list = ["loadfile", path, "replace"]
        if start_pos > 0.0:
            load_cmd.extend(["0", str(start_pos)])
        await self._send_command(load_cmd)
        await self._send_command(["set_property", "pause", False])
        if muted:
            await self._send_command(["set_property", "mute", True])
        else:
            await self._send_command(["set_property", "mute", False])
        if artist or title:
            await self._send_command(
                [
                    "set_property",
                    "metadata",
                    {"Artist": artist or "—", "Title": media_title},
                ]
            )
        self._apply_play_state(path, title=title, artist=artist, media_title=media_title)

    def _apply_play_state(
        self,
        path: str,
        *,
        title: str,
        artist: str,
        media_title: str,
    ) -> None:
        p = Path(path)
        self.state.path = path
        if title:
            self.state.title = title[:40]
        elif path.startswith(("http://", "https://")):
            self.state.title = "Streaming"
        else:
            self.state.title = p.stem if p.stem else media_title[:40]
        self.state.artist = artist if artist else "—"
        self.state.status = PlaybackStatus.PLAYING
        self.state.paused = False

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
            await self._send_command(["set_property", "volume", vol])

    async def set_mute(self, muted: bool) -> None:
        if self._writer:
            await self._send_command(["set_property", "mute", muted])

    async def stop(self) -> None:
        """Kill mpv and reset state."""
        saved_volume = self.state.volume
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
        self.state.volume = saved_volume
        self._properties_observed = False

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
        executable = _mpv_executable()
        if not executable:
            return False
        try:
            subprocess.run(
                [executable, "--version"],
                capture_output=True,
                timeout=5,
                check=True,
            )
            return True
        except (OSError, subprocess.SubprocessError):
            return False

    async def _connect_ipc(self) -> bool:
        sock_path = Path(IPC_SOCKET)
        for _ in range(30):  # Wait up to ~1.5 s
            if sock_path.exists():
                try:
                    self._reader, self._writer = await asyncio.open_unix_connection(
                        str(sock_path)
                    )
                    self._listener_task = asyncio.create_task(self._listen())
                    return True
                except Exception:
                    await asyncio.sleep(0.05)
                    continue
            await asyncio.sleep(0.05)
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
        except asyncio.CancelledError:
            pass
        except Exception:
            pass
        finally:
            self._writer = None
            self._reader = None
            self._listener_task = None
            self._on_mpv_disconnected()

    def _on_mpv_disconnected(self) -> None:
        """Sync state when the audio subprocess closes IPC or crashes."""
        if self._process is not None and self._process.poll() is not None:
            self._process = None
        self._properties_observed = False
        if self.state.status != PlaybackStatus.STOPPED:
            self.state.status = PlaybackStatus.STOPPED
            self.state.time_pos = 0.0

    def sync_process_state(self) -> None:
        """Detect a dead mpv process missed by the IPC listener."""
        if self._process is None or self._process.poll() is None:
            return
        self._on_mpv_disconnected()

    async def _dispatch(self, msg: dict) -> None:
        rid = msg.get("request_id")
        if rid is not None:
            fut = self._pending.pop(str(rid), None)
            if fut and not fut.done():
                fut.set_result(msg)
        if "event" in msg:
            ev = msg["event"]
            if ev == "end-file":
                reason = msg.get("reason", _END_FILE_EOF)
                self.state.status = PlaybackStatus.STOPPED
                self.state.time_pos = 0.0
                # Only auto-advance on natural EOF; explicit stop must not race it.
                if reason == _END_FILE_EOF and self._on_end_file:
                    self._on_end_file()
            elif ev == "shutdown":
                self.state.status = PlaybackStatus.STOPPED
                self.state.time_pos = 0.0
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
        except Exception:
            self._pending.pop(str(self._req_id), None)
            return {"error": "disconnected"}

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
        self._timer.setInterval(500)
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
        title: str = "",
        artist: str = "",
        *,
        volume: int | None = None,
        muted: bool = False,
        start_pos: float = 0.0,
    ) -> None:
        asyncio.ensure_future(
            self._player.play(
                path,
                title=title,
                artist=artist,
                volume=volume,
                muted=muted,
                start_pos=start_pos,
            )
        )

    def toggle_pause(self) -> None:
        asyncio.ensure_future(self._player.toggle_pause())

    def seek(self, delta: float) -> None:
        asyncio.ensure_future(self._player.seek(delta))

    def seek_absolute(self, position: float) -> None:
        asyncio.ensure_future(self._player.seek_absolute(position))

    def set_volume(self, vol: int) -> None:
        asyncio.ensure_future(self._player.set_volume(vol))

    def set_mute(self, muted: bool) -> None:
        asyncio.ensure_future(self._player.set_mute(muted))

    def stop(self) -> None:
        asyncio.ensure_future(self._player.stop())

    def cleanup_sync(self) -> None:
        self._timer.stop()
        self._player.cleanup_sync()

    def _poll(self) -> None:
        """Emit signals if state has changed since last poll."""
        self._player.sync_process_state()
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
        # Defer so we never auto-advance/replay from inside the IPC listener task.
        QTimer.singleShot(0, self.track_ended.emit)

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
