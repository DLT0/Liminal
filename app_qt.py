"""Liminal — Local Media Player (PyQt6 GUI)."""

import sys
import asyncio
from pathlib import Path

import qasync
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from src.player import PlayerBridge
from src.qt.main_window import MainWindow

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
    window = MainWindow(player)
    window.show()

    with loop:
        loop.run_forever()


if __name__ == "__main__":
    main()
