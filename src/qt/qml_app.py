"""Launch Liminal with QML UI."""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QIcon
from PyQt6.QtQml import QQmlApplicationEngine, qmlRegisterSingletonType
from PyQt6.QtWidgets import QApplication

from src.player import PlayerBridge
from src.qt.qml_backend import AppBackend

QML_DIR = Path(__file__).resolve().parents[1] / "qml"
THEME_QML = (QML_DIR / "Liminal" / "Theme.qml").resolve()
ICON_PATH = Path(__file__).resolve().parent / "liminal.png"

# Keep engine alive for app lifetime
_engine: QQmlApplicationEngine | None = None
_theme_registered = False


def _register_theme() -> None:
    """Register Theme singleton explicitly (reliable across Qt installs)."""
    global _theme_registered
    if _theme_registered:
        return
    if not THEME_QML.exists():
        print(f"Missing Theme.qml: {THEME_QML}", file=sys.stderr)
        sys.exit(1)
    qmlRegisterSingletonType(
        QUrl.fromLocalFile(str(THEME_QML)),
        "Liminal",
        1,
        0,
        "Theme",
    )
    _theme_registered = True


def run_qml_app(app: QApplication, player: PlayerBridge) -> None:
    global _engine

    _register_theme()

    _engine = QQmlApplicationEngine()
    _engine.addImportPath(str(QML_DIR.resolve()))

    backend = AppBackend(player)
    backend.setParent(_engine)
    _engine.rootContext().setContextProperty("backend", backend)

    _engine.load(QUrl.fromLocalFile(str((QML_DIR / "main.qml").resolve())))

    if not _engine.rootObjects():
        print("Failed to load QML UI.", file=sys.stderr)
        sys.exit(1)

    app.aboutToQuit.connect(backend.cleanup)
