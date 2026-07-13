"""Launch Liminal with QML UI."""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import QTimer, QUrl
from PyQt6.QtGui import QIcon, QWindow
from PyQt6.QtQml import QQmlApplicationEngine, qmlRegisterSingletonType
from PyQt6.QtWidgets import QApplication

from src.player import PlayerBridge
from src.mpris_service import MprisService
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
    mpris: MprisService | None = None,
) -> AppBackend:
    """Load QML and backend while intro may still be playing. Window stays hidden."""
    global _engine

    _register_theme()
    app.setQuitOnLastWindowClosed(False)

    _engine = QQmlApplicationEngine()
    _engine.addImportPath(str(QML_DIR.resolve()))

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

    if mpris is not None:
        mpris.set_transport_handlers(backend.next, backend.previous)
    _engine.rootContext().setContextProperty("backend", backend)
    _engine.rootContext().setContextProperty("mpvVideo", mpv_video)
    _engine.rootContext().setContextProperty("shareBridge", share_bridge)
    _engine.rootContext().setContextProperty("uiConfig", ui_bridge)

    _engine.load(QUrl.fromLocalFile(str((QML_DIR / "main.qml").resolve())))

    if not _engine.rootObjects():
        print("Failed to load QML UI.", file=sys.stderr)
        sys.exit(1)

    root = _engine.rootObjects()[0]
    if isinstance(root, QWindow):
        backend.set_main_window(root)
        mpv_video.setMainWindow(root)

    from PyQt6.QtGui import QAction
    from PyQt6.QtWidgets import QMenu, QSystemTrayIcon

    tray_icon = QSystemTrayIcon(QIcon(str(ICON_PATH)), app)
    tray_icon.setToolTip("Liminal Media Player")

    tray_menu = QMenu()
    show_action = QAction("Hiện ứng dụng", app)
    quit_action = QAction("Thoát", app)

    tray_menu.addAction(show_action)
    tray_menu.addSeparator()
    tray_menu.addAction(quit_action)

    tray_icon.setContextMenu(tray_menu)
    tray_icon.show()

    show_action.triggered.connect(backend.restoreFromTray)

    def quit_from_tray() -> None:
        tray_icon.hide()
        backend.quitApp()

    quit_action.triggered.connect(quit_from_tray)

    def on_tray_activated(reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            backend.restoreFromTray()

    tray_icon.activated.connect(on_tray_activated)

    QTimer.singleShot(0, backend.load_initial_page)
    QTimer.singleShot(0, share_bridge.emit_cached_shared)
    QTimer.singleShot(0, share_bridge.refreshShared)

    import atexit

    atexit.register(backend._player.cleanup_sync)
    atexit.register(mpv_video.cleanup_sync)

    return backend


def show_qml_app(backend: AppBackend) -> None:
    """Reveal the main window after intro (or other splash) completes."""
    backend.show_main_window()


def run_qml_app(
    app: QApplication,
    player: PlayerBridge,
    mpris: MprisService | None = None,
) -> AppBackend:
    backend = prepare_qml_app(app, player, mpris)
    show_qml_app(backend)
    return backend
