"""Liminal — Local Media Player (PyQt6 GUI)."""

import os
import sys
import asyncio
import locale
import logging
from pathlib import Path

import qasync
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

from src.player import PlayerBridge
from src.qt.qml_app import run_qml_app

ICON_PATH = Path(__file__).resolve().parent / "src" / "qt" / "liminal.png"


def _configure_platform() -> None:
    """Prefer xcb on XWayland so mpv --wid embedding works on GNOME Wayland."""
    # Suppress verbose FFmpeg warnings (e.g. "Could not update timestamps for skipped samples")
    if "AV_LOG_LEVEL" not in os.environ:
        os.environ["AV_LOG_LEVEL"] = "error"
    # Suppress Qt Multimedia and dbus service warnings
    if "QT_LOGGING_RULES" not in os.environ:
        os.environ["QT_LOGGING_RULES"] = "qt.multimedia*=error;qt.qpa.services=error"

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


def _prewarm_qt_multimedia(app: QApplication) -> None:
    """Load GStreamer/Qt Multimedia plugins during startup to speed first video open."""
    try:
        from PyQt6.QtCore import QUrl
        from PyQt6.QtMultimedia import QMediaPlayer

        player = QMediaPlayer(app)
        player.setSource(QUrl())
        player.stop()
    except Exception:
        pass


def main() -> None:
    _configure_platform()
    _configure_multimedia_fallback()
    # Respect LIMINAL_LOG_LEVEL env var, default to INFO
    log_level = os.environ.get("LIMINAL_LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    # Keep Qt and multimedia libraries on the C numeric locale.
    locale.setlocale(locale.LC_NUMERIC, "C")
    app = QApplication(sys.argv)
    app.setApplicationName("Liminal")
    app.setDesktopFileName("liminal")
    _prewarm_qt_multimedia(app)
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
    backend_ref = run_qml_app(app, player)

    def handle_new_connection():
        client = server.nextPendingConnection()
        if client:
            def read_data():
                nonlocal client
                data = client.readAll().data()
                if b"show" in data and backend_ref:
                    backend_ref.show_main_window()
            client.readyRead.connect(read_data)

    server.newConnection.connect(handle_new_connection)

    with loop:
        loop.run_forever()


if __name__ == "__main__":
    main()
