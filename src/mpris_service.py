"""MPRIS D-Bus — dbus-python with GLib mainloop, correct signal typing."""

from __future__ import annotations

import logging
from typing import Callable, Optional

import dbus
import dbus.lowlevel
import dbus.service
from gi.repository import GLib
from PyQt6.QtCore import QObject, QTimer

from src.models import PlaybackState, PlaybackStatus
from src.player import PlayerBridge

logger = logging.getLogger(__name__)

BUS_NAME = "org.mpris.MediaPlayer2.liminal"
OBJ_PATH = "/org/mpris/MediaPlayer2"
TRACK_ID = "/org/liminal/CurrentTrack"

PLAYER_IFACE = "org.mpris.MediaPlayer2.Player"
ROOT_IFACE = "org.mpris.MediaPlayer2"
PROPS_IFACE = "org.freedesktop.DBus.Properties"


def _status_name(status: PlaybackStatus) -> str:
    return ("Playing" if status == PlaybackStatus.PLAYING
            else "Paused" if status == PlaybackStatus.PAUSED
            else "Stopped")


class _MprisObj(dbus.service.Object):
    """MPRIS D-Bus object (Root + Player interfaces)."""

    def __init__(self, player: PlayerBridge) -> None:
        from dbus.mainloop.glib import DBusGMainLoop
        DBusGMainLoop(set_as_default=True)
        self._bus = dbus.SessionBus()
        bus_name = dbus.service.BusName(BUS_NAME, bus=self._bus)
        super().__init__(bus_name, OBJ_PATH)
        self._player = player
        self._on_next: Optional[Callable[[], None]] = None
        self._on_previous: Optional[Callable[[], None]] = None
        self._last_status = ""
        self._last_pos = -1
        self._last_meta: dict = {}

        player.state_changed.connect(self._on_state)
        player.position_changed.connect(self._on_pos)

        self._timer = QTimer()
        self._timer.setInterval(500)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

        # Iterate GLib to dispatch pending D-Bus registration/calls
        for _ in range(10):
            GLib.MainContext.default().iteration(False)

    def set_transport(self, nxt: Callable, prev: Callable) -> None:
        self._on_next = nxt
        self._on_previous = prev

    # -- State & signal emission --

    def _build_meta(self) -> dict:
        s = self._player.state
        artist = s.artist if s.artist and s.artist != "—" else "Unknown Artist"
        return {
            "xesam:title": s.title or "Nothing playing",
            "xesam:artist": [artist],
            "mpris:trackid": TRACK_ID,
            "mpris:length": int(max(0.0, s.duration) * 1_000_000),
            "xesam:url": s.path or "",
        }

    def _emit(self, changes: dict) -> None:
        if not changes:
            return
        try:
            props = {}
            for key, val in changes.items():
                if key == "PlaybackStatus":
                    props[key] = dbus.String(val, variant_level=1)
                elif key == "Position":
                    props[key] = dbus.Int64(val, variant_level=1)
                elif key == "Metadata":
                    meta = {}
                    for mk, mv in val.items():
                        if mk == "xesam:artist":
                            meta[mk] = dbus.Array(
                                [dbus.String(a) for a in mv],
                                signature="s", variant_level=1,
                            )
                        elif mk == "mpris:length":
                            meta[mk] = dbus.Int64(mv, variant_level=1)
                        else:
                            meta[mk] = dbus.String(str(mv), variant_level=1)
                    props[key] = dbus.Dictionary(meta, signature="sv", variant_level=1)
            msg = dbus.lowlevel.SignalMessage(
                OBJ_PATH, PROPS_IFACE, "PropertiesChanged",
            )
            msg.append(
                PLAYER_IFACE,
                dbus.Dictionary(props, signature="sv"),
                dbus.Array([], signature="s"),
                signature="sa{sv}as",
            )
            # Use the same connection that owns BUS_NAME
            self._bus.send_message(msg)
        except Exception:
            logger.warning("MPRIS: emit failed", exc_info=True)

    def _on_state(self, state: PlaybackState) -> None:
        c: dict = {}
        s = _status_name(state.status)
        if s != self._last_status:
            c["PlaybackStatus"] = s
            self._last_status = s
        meta = self._build_meta()
        if meta != self._last_meta:
            c["Metadata"] = meta
            self._last_meta = meta
        self._emit(c)

    def _on_pos(self, _t: float, _d: float) -> None:
        # D-Bus position dispatch is handled by the _tick timer
        pass

    def _tick(self) -> None:
        pos = int(max(0.0, self._player.state.time_pos) * 1_000_000)
        if abs(pos - self._last_pos) > 500_000:
            self._last_pos = pos
            self._emit({"Position": pos})
        # Iterate GLib a few times for D-Bus method call dispatch
        for _ in range(2):
            GLib.MainContext.default().iteration(False)

    # -- Properties --

    def _root_all(self) -> dict:
        return {
            "CanQuit": False, "CanRaise": True, "HasTrackList": False,
            "Identity": "Liminal", "DesktopEntry": "liminal",
            "SupportedUriSchemes": dbus.Array(["file", "http", "https"], signature="s"),
            "SupportedMimeTypes": dbus.Array([], signature="s"),
        }

    def _player_all(self) -> dict:
        s = self._player.state
        artist = s.artist if s.artist and s.artist != "—" else "Unknown Artist"
        meta = dbus.Dictionary({
            "xesam:title": dbus.String(s.title or "Nothing playing"),
            "xesam:artist": dbus.Array([artist], signature="s"),
            "mpris:trackid": dbus.ObjectPath(TRACK_ID),
            "mpris:length": dbus.Int64(int(max(0.0, s.duration) * 1_000_000)),
            "xesam:url": dbus.String(s.path or ""),
        }, signature="sv")
        return {
            "PlaybackStatus": _status_name(s.status),
            "Metadata": meta,
            "Position": dbus.Int64(int(max(0.0, s.time_pos) * 1_000_000)),
            "CanPlay": True, "CanPause": True,
            "CanGoNext": self._on_next is not None,
            "CanGoPrevious": self._on_previous is not None,
            "CanSeek": True, "CanControl": True,
            "Rate": 1.0, "MinimumRate": 1.0, "MaximumRate": 1.0,
            "LoopStatus": "None", "Shuffle": False,
            "Volume": s.volume / 100.0,
        }

    @dbus.service.method(PROPS_IFACE, in_signature="ss", out_signature="v")
    def Get(self, interface: str, prop: str):
        src = self._root_all if interface == ROOT_IFACE else self._player_all
        m = src()
        if prop not in m:
            raise dbus.exceptions.DBusException(
                "org.freedesktop.DBus.Error.InvalidArgs",
                f"Unknown property {interface}.{prop}",
            )
        return m[prop]

    @dbus.service.method(PROPS_IFACE, in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface: str):
        src = self._root_all if interface == ROOT_IFACE else self._player_all
        return dbus.Dictionary(src(), signature="sv")

    @dbus.service.method(ROOT_IFACE, in_signature="", out_signature="")
    def Raise(self) -> None: pass

    @dbus.service.method(ROOT_IFACE, in_signature="", out_signature="")
    def Quit(self) -> None: pass

    @dbus.service.method(PLAYER_IFACE, in_signature="", out_signature="")
    def Play(self) -> None:
        if self._player.state.status == PlaybackStatus.PAUSED:
            self._player.toggle_pause()

    @dbus.service.method(PLAYER_IFACE, in_signature="", out_signature="")
    def Pause(self) -> None:
        if self._player.state.status == PlaybackStatus.PLAYING:
            self._player.toggle_pause()

    @dbus.service.method(PLAYER_IFACE, in_signature="", out_signature="")
    def PlayPause(self) -> None:
        if self._player.state.status != PlaybackStatus.STOPPED:
            self._player.toggle_pause()

    @dbus.service.method(PLAYER_IFACE, in_signature="", out_signature="")
    def Stop(self) -> None: self._player.stop()

    @dbus.service.method(PLAYER_IFACE, in_signature="", out_signature="")
    def Next(self) -> None:
        if self._on_next: self._on_next()

    @dbus.service.method(PLAYER_IFACE, in_signature="", out_signature="")
    def Previous(self) -> None:
        if self._on_previous: self._on_previous()

    @dbus.service.method(PLAYER_IFACE, in_signature="x", out_signature="")
    def Seek(self, us: int) -> None:
        self._player.seek(us / 1_000_000)

    @dbus.service.method(PLAYER_IFACE, in_signature="ox", out_signature="")
    def SetPosition(self, _tid: dbus.ObjectPath, us: int) -> None:
        self._player.seek_absolute(max(0.0, us / 1_000_000))

    @dbus.service.method(PLAYER_IFACE, in_signature="s", out_signature="")
    def OpenUri(self, uri: str) -> None:
        """Handle external OpenUri requests without ever spawning video UI."""
        from urllib.parse import unquote, urlparse
        p = urlparse(uri)
        if p.scheme == "file":
            self._player.play(unquote(p.path))
        elif p.scheme in ("http", "https"):
            self._player.play(uri)


class MprisService(QObject):
    """Register Liminal on session bus for playerctl/waybar."""

    def __init__(self, player: PlayerBridge, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._obj = _MprisObj(player)
        logger.info("MPRIS on bus as %s", BUS_NAME)

    def set_transport_handlers(self, nxt: Callable, prev: Callable) -> None:
        self._obj.set_transport(nxt, prev)

    def shutdown(self) -> None:
        try:
            self._obj._bus.release_name(BUS_NAME)
        except Exception:
            pass
