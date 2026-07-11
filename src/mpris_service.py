"""MPRIS D-Bus bridge so playerctl/waybar can show Liminal playback."""

from __future__ import annotations

import logging
from typing import Callable, Optional

from PyQt6.QtCore import QObject, pyqtClassInfo, pyqtProperty, pyqtSignal, pyqtSlot
from PyQt6.QtDBus import QDBusAbstractAdaptor, QDBusConnection

from src.models import PlaybackState, PlaybackStatus
from src.player import PlayerBridge

logger = logging.getLogger(__name__)

MPRIS_SERVICE = "org.mpris.MediaPlayer2.liminal"
MPRIS_PATH = "/org/mpris/MediaPlayer2"
TRACK_ID = "/org/liminal/CurrentTrack"


def _status_name(status: PlaybackStatus) -> str:
    if status == PlaybackStatus.PLAYING:
        return "Playing"
    if status == PlaybackStatus.PAUSED:
        return "Paused"
    return "Stopped"


class _MprisRootAdaptor(QDBusAbstractAdaptor):
    pyqtClassInfo("D-Bus Interface", "org.mpris.MediaPlayer2")

    def __init__(self, parent: "MprisPlayer") -> None:
        super().__init__(parent)
        self.setAutoRelaySignals(True)


class _MprisPlayerAdaptor(QDBusAbstractAdaptor):
    pyqtClassInfo("D-Bus Interface", "org.mpris.MediaPlayer2.Player")

    def __init__(self, parent: "MprisPlayer") -> None:
        super().__init__(parent)
        self.setAutoRelaySignals(True)


class MprisPlayer(QObject):
    """MPRIS player object exported on the session bus."""

    playback_status_changed = pyqtSignal(str)
    metadata_changed = pyqtSignal("QVariantMap")
    position_changed = pyqtSignal(int)

    def __init__(
        self,
        player: PlayerBridge,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._player = player
        self._on_next: Optional[Callable[[], None]] = None
        self._on_previous: Optional[Callable[[], None]] = None

        self._playback_status = "Stopped"
        self._metadata: dict = {}
        self._position_us = 0

        _MprisRootAdaptor(self)
        _MprisPlayerAdaptor(self)

        player.state_changed.connect(self._on_state_changed)
        player.position_changed.connect(self._on_position_changed)

    def set_transport_handlers(
        self,
        on_next: Callable[[], None],
        on_previous: Callable[[], None],
    ) -> None:
        self._on_next = on_next
        self._on_previous = on_previous

    @pyqtProperty(bool, constant=True)
    def CanQuit(self) -> bool:
        return False

    @pyqtProperty(bool, constant=True)
    def CanRaise(self) -> bool:
        return True

    @pyqtProperty(bool, constant=True)
    def HasTrackList(self) -> bool:
        return False

    @pyqtProperty(str, constant=True)
    def Identity(self) -> str:
        return "Liminal"

    @pyqtProperty(str, constant=True)
    def DesktopEntry(self) -> str:
        return "liminal"

    @pyqtProperty("QStringList", constant=True)
    def SupportedUriSchemes(self) -> list[str]:
        return ["file", "http", "https"]

    @pyqtProperty("QStringList", constant=True)
    def SupportedMimeTypes(self) -> list[str]:
        return []

    @pyqtSlot()
    def Raise(self) -> None:
        pass

    @pyqtSlot()
    def Quit(self) -> None:
        pass

    @pyqtProperty(str, notify=playback_status_changed)
    def PlaybackStatus(self) -> str:
        return self._playback_status

    @pyqtProperty("QVariantMap", notify=metadata_changed)
    def Metadata(self) -> dict:
        return self._metadata

    @pyqtProperty(int, notify=position_changed)
    def Position(self) -> int:
        return self._position_us

    @pyqtProperty(bool, constant=True)
    def CanPlay(self) -> bool:
        return True

    @pyqtProperty(bool, constant=True)
    def CanPause(self) -> bool:
        return True

    @pyqtProperty(bool, constant=True)
    def CanSeek(self) -> bool:
        return True

    @pyqtProperty(bool, constant=True)
    def CanControl(self) -> bool:
        return True

    @pyqtProperty(bool, constant=True)
    def CanGoNext(self) -> bool:
        return self._on_next is not None

    @pyqtProperty(bool, constant=True)
    def CanGoPrevious(self) -> bool:
        return self._on_previous is not None

    @pyqtProperty(float, constant=True)
    def Rate(self) -> float:
        return 1.0

    @pyqtProperty(float, constant=True)
    def MinimumRate(self) -> float:
        return 1.0

    @pyqtProperty(float, constant=True)
    def MaximumRate(self) -> float:
        return 1.0

    @pyqtProperty(str, constant=True)
    def LoopStatus(self) -> str:
        return "None"

    @pyqtProperty(bool, constant=True)
    def Shuffle(self) -> bool:
        return False

    @pyqtSlot()
    def Play(self) -> None:
        state = self._player.state
        if state.status == PlaybackStatus.PAUSED:
            self._player.toggle_pause()

    @pyqtSlot()
    def Pause(self) -> None:
        state = self._player.state
        if state.status == PlaybackStatus.PLAYING:
            self._player.toggle_pause()

    @pyqtSlot()
    def PlayPause(self) -> None:
        if self._player.state.status != PlaybackStatus.STOPPED:
            self._player.toggle_pause()

    @pyqtSlot()
    def Stop(self) -> None:
        self._player.stop()

    @pyqtSlot()
    def Next(self) -> None:
        if self._on_next:
            self._on_next()

    @pyqtSlot()
    def Previous(self) -> None:
        if self._on_previous:
            self._on_previous()

    @pyqtSlot(int)
    def Seek(self, offset_us: int) -> None:
        self._player.seek(offset_us / 1_000_000)

    @pyqtSlot(str, int)
    def SetPosition(self, _track_id: str, position_us: int) -> None:
        self._player.seek_absolute(max(0.0, position_us / 1_000_000))

    @pyqtSlot(str)
    def OpenUri(self, _uri: str) -> None:
        pass

    def _on_state_changed(self, state: PlaybackState) -> None:
        status = _status_name(state.status)
        if status != self._playback_status:
            self._playback_status = status
            self.playback_status_changed.emit(status)

        artist = state.artist if state.artist and state.artist != "—" else "Unknown Artist"
        title = state.title or "Nothing playing"
        length_us = int(max(0.0, state.duration) * 1_000_000)

        metadata = {
            "xesam:title": title,
            "xesam:artist": [artist],
            "mpris:trackid": TRACK_ID,
            "mpris:length": length_us,
        }
        if state.path:
            metadata["xesam:url"] = state.path

        if metadata != self._metadata:
            self._metadata = metadata
            self.metadata_changed.emit(metadata)

        self._update_position(state.time_pos)

    def _on_position_changed(self, time_pos: float, _duration: float) -> None:
        self._update_position(time_pos)

    def _update_position(self, time_pos: float) -> None:
        position_us = int(max(0.0, time_pos) * 1_000_000)
        if position_us != self._position_us:
            self._position_us = position_us
            self.position_changed.emit(position_us)


class MprisService:
    """Register Liminal on the session D-Bus for playerctl integration."""

    def __init__(self, player: PlayerBridge) -> None:
        self._mpris = MprisPlayer(player)
        self._bus = QDBusConnection.sessionBus()

        if not self._bus.registerObject(
            MPRIS_PATH,
            self._mpris,
            QDBusConnection.RegisterOption.ExportAllContents,
        ):
            logger.warning("MPRIS: failed to register object at %s", MPRIS_PATH)
            return

        if not self._bus.registerService(MPRIS_SERVICE):
            logger.warning("MPRIS: failed to register service %s", MPRIS_SERVICE)
            return

        logger.info("MPRIS registered as %s", MPRIS_SERVICE)

    def set_transport_handlers(
        self,
        on_next: Callable[[], None],
        on_previous: Callable[[], None],
    ) -> None:
        self._mpris.set_transport_handlers(on_next, on_previous)

    def shutdown(self) -> None:
        if self._bus.isConnected():
            self._bus.unregisterService(MPRIS_SERVICE)
            self._bus.unregisterObject(MPRIS_PATH)
