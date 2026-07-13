"""Liminal — Local Media Player (PyQt6 GUI)."""

import os
import sys
import asyncio
import locale
from pathlib import Path

import qasync
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

from src.player import PlayerBridge
from src.qt.qml_app import prepare_qml_app, show_qml_app

ICON_PATH = Path(__file__).resolve().parent / "src" / "qt" / "liminal.png"


def _create_mpris_service(player: PlayerBridge):
    """Register MPRIS when dbus/gi are available (pip or distro packages)."""
    try:
        from src.mpris_service import MprisService
    except ImportError:
        return None
    try:
        return MprisService(player)
    except Exception:
        return None


def _configure_platform() -> None:
    """Prefer xcb on XWayland so mpv --wid embedding works on GNOME Wayland."""
    if (
        not os.environ.get("QT_QPA_PLATFORM")
        and os.environ.get("WAYLAND_DISPLAY")
        and os.environ.get("DISPLAY")
    ):
        os.environ["QT_QPA_PLATFORM"] = "xcb"


def _configure_multimedia_fallback() -> None:
    """Tune GStreamer for Qt Multimedia when mpv is unavailable."""
    if "GST_PLUGIN_FEATURE_RANK" not in os.environ:
        os.environ["GST_PLUGIN_FEATURE_RANK"] = (
            "nvh264dec:PRIMARY,nvdec:PRIMARY,nvh265dec:PRIMARY,"
            "vah264dec:PRIMARY,vaapidecodebin:PRIMARY,"
            "v4l2h264dec:PRIMARY"
        )


def main() -> None:
    _configure_platform()
    _configure_multimedia_fallback()
    # Keep Qt and multimedia libraries on the C numeric locale.
    locale.setlocale(locale.LC_NUMERIC, "C")
    app = QApplication(sys.argv)
    app.setApplicationName("Liminal")
    app.setDesktopFileName("liminal")
    if ICON_PATH.exists():
        app.setWindowIcon(QIcon(str(ICON_PATH)))

    # Single Instance Logic using QLocalServer/QLocalSocket
    socket_name = "liminal-single-instance-lock"
    socket = QLocalSocket()
    socket.connectToServer(socket_name)
    if socket.waitForConnected(500):
        # Already running! Request display show and exit
        socket.write(b"show")
        socket.waitForBytesWritten(500)
        socket.disconnectFromServer()
        print("Liminal is already running. Activating the existing instance.")
        sys.exit(0)

    # First instance: setup server lock
    QLocalServer.removeServer(socket_name)
    server = QLocalServer()
    if not server.listen(socket_name):
        print("Failed to start local single instance server.")

    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    player = PlayerBridge()
    mpris = _create_mpris_service(player)

    # Preload QML during intro so the main window appears as soon as intro ends.
    from src.qt.intro_splash import IntroSplash

    intro = IntroSplash("src/qt/app_intro.mp4")

    backend_ref = None
    intro_done = False
    qml_ready = False
    main_shown = False

    def _try_show_main() -> None:
        nonlocal main_shown
        if main_shown or not intro_done or not qml_ready or backend_ref is None:
            return
        main_shown = True
        show_qml_app(backend_ref)

    def _on_intro_finished() -> None:
        nonlocal intro_done
        intro_done = True
        _try_show_main()

    def _on_qml_prepared() -> None:
        nonlocal backend_ref, qml_ready
        backend_ref = prepare_qml_app(app, player, mpris)
        qml_ready = True
        _try_show_main()

    intro.finished.connect(_on_intro_finished)
    if mpris is not None:
        app.aboutToQuit.connect(mpris.shutdown)
    intro.start()
    QTimer.singleShot(0, _on_qml_prepared)

    def handle_new_connection():
        client = server.nextPendingConnection()
        if client:
            def read_data():
                nonlocal client
                data = client.readAll().data()
                if b"show" in data and backend_ref:
                    backend_ref.restoreFromTray()
            client.readyRead.connect(read_data)

    server.newConnection.connect(handle_new_connection)

    with loop:
        loop.run_forever()


if __name__ == "__main__":
    main()
