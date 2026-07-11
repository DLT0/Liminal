"""Liminal — Local Media Player (PyQt6 GUI)."""

import sys
import asyncio
from pathlib import Path

import qasync
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

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

    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    player = PlayerBridge()
    mpris = MprisService(player)

    # Launch IntroSplash first. When it finishes, display QML UI.
    from src.qt.intro_splash import IntroSplash

    intro = IntroSplash("src/qt/app_intro.mp4")

    def _show_main() -> None:
        run_qml_app(app, player, mpris)

    intro.finished.connect(_show_main)
    app.aboutToQuit.connect(mpris.shutdown)
    intro.start()

    with loop:
        loop.run_forever()


if __name__ == "__main__":
    main()
