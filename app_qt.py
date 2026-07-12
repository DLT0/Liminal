"""Liminal — Local Media Player (PyQt6 GUI)."""

import sys
import asyncio
from pathlib import Path

import qasync
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

from src.player import PlayerBridge
from src.mpris_service import MprisService
from src.qt.qml_app import run_qml_app

ICON_PATH = Path(__file__).resolve().parent / "src" / "qt" / "liminal.png"


def main() -> None:
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
    mpris = MprisService(player)

    # Launch IntroSplash first. When it finishes, display QML UI.
    from src.qt.intro_splash import IntroSplash

    intro = IntroSplash("src/qt/app_intro.mp4")
    
    # Store backend reference for the instance server
    backend_ref = None

    def _show_main() -> None:
        nonlocal backend_ref
        backend_ref = run_qml_app(app, player, mpris)

    intro.finished.connect(_show_main)
    app.aboutToQuit.connect(mpris.shutdown)
    intro.start()

    def handle_new_connection():
        client = server.nextPendingConnection()
        if client:
            def read_data():
                nonlocal client
                data = client.readAll().data()
                if b"show" in data and backend_ref and backend_ref._main_window:
                    backend_ref._main_window.show()
                    backend_ref._main_window.raise_()
                    backend_ref._main_window.requestActivate()
            client.readyRead.connect(read_data)

    server.newConnection.connect(handle_new_connection)

    with loop:
        loop.run_forever()


if __name__ == "__main__":
    main()
