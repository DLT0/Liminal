"""Launch Liminal with QML UI."""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import QTimer, QUrl
from PyQt6.QtGui import QIcon, QImage, QWindow
from PyQt6.QtQml import QQmlApplicationEngine, qmlRegisterSingletonType
from PyQt6.QtQuick import QQuickImageProvider
from PyQt6.QtWidgets import QApplication

from src.player import PlayerBridge
from src.qt.mpv_video_bridge import MpvVideoBridge
from src.qt.share_bridge import ShareBridge
from src.qt.qml_backend import AppBackend
from src.ui_config import UiConfigBridge, load_ui_config

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


def prepare_qml_app(
    app: QApplication,
    player: PlayerBridge,
) -> AppBackend:
    """Load QML engine and backend. Window stays hidden until show_qml_app."""
    global _engine

    _register_theme()
    # Closing the only window must terminate the application.
    app.setQuitOnLastWindowClosed(True)

    _engine = QQmlApplicationEngine()
    _engine.addImportPath(str(QML_DIR.resolve()))

    # Register book page image provider
    class BookPageProvider(QQuickImageProvider):
        def __init__(self):
            super().__init__(QQuickImageProvider.ImageType.Image)
        def requestImage(self, id: str, size, requestedSize):
            from src.ebook_reader import render_page
            parts = id.split("/")
            path = "/".join(parts[:-2])
            try:
                page_num = int(parts[-2])
                zoom = float(parts[-1])
            except (IndexError, ValueError):
                return QImage()
            result = render_page(path, page_num, zoom)
            if result:
                return QImage(result)
            return QImage()
    _engine.addImageProvider("bookpage", BookPageProvider())

    ui_config = load_ui_config()
    ui_bridge = UiConfigBridge(ui_config)
    ui_bridge.setParent(_engine)

    mpv_video = MpvVideoBridge()
    mpv_video.setParent(_engine)

    backend = AppBackend(player, ui_config=ui_config)
    backend.set_engine(_engine)
    backend.setParent(_engine)

    share_bridge = ShareBridge()
    share_bridge.set_backend(backend)
    share_bridge.setParent(_engine)

    _engine.rootContext().setContextProperty("backend", backend)
    _engine.rootContext().setContextProperty("mpvVideo", mpv_video)
    _engine.rootContext().setContextProperty("shareBridge", share_bridge)
    _engine.rootContext().setContextProperty("uiConfig", ui_bridge)
    ui_bridge.settingsFileChanged.connect(backend.reload_app_settings_from_disk)

    _engine.load(QUrl.fromLocalFile(str((QML_DIR / "main.qml").resolve())))

    if not _engine.rootObjects():
        print("Failed to load QML UI.", file=sys.stderr)
        sys.exit(1)

    root = _engine.rootObjects()[0]
    if isinstance(root, QWindow):
        backend.set_main_window(root)
        mpv_video.setMainWindow(root)

    QTimer.singleShot(0, backend.preload_libraries)
    QTimer.singleShot(0, backend.load_initial_page)
    QTimer.singleShot(0, share_bridge.emit_cached_shared)
    QTimer.singleShot(0, share_bridge.refreshShared)
    QTimer.singleShot(0, share_bridge.emit_cached_suggestions)
    QTimer.singleShot(250, share_bridge.refreshSuggestions)

    import atexit

    atexit.register(backend._player.cleanup_sync)
    atexit.register(mpv_video.cleanup_sync)

    return backend


def show_qml_app(backend: AppBackend) -> None:
    """Reveal the main window."""
    backend.show_main_window()


def run_qml_app(
    app: QApplication,
    player: PlayerBridge,
) -> AppBackend:
    backend = prepare_qml_app(app, player)
    show_qml_app(backend)
    return backend
