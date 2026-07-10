"""Liminal — Local Media Player (PyQt6 GUI)."""

import sys
import asyncio

import qasync
from PyQt6.QtWidgets import QApplication

from src.player import PlayerBridge
from src.qt.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Liminal")

    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    player = PlayerBridge()
    window = MainWindow(player)
    window.show()

    with loop:
        loop.run_forever()


if __name__ == "__main__":
    main()
