"""Resolve UI appearance from ~/.config/liminal/settings.json (VS Code-style keys)."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path

from PyQt6.QtCore import QObject, QTimer, QFileSystemWatcher, pyqtProperty, pyqtSignal, pyqtSlot, QUrl
from PyQt6.QtGui import QDesktopServices

from src.settings_store import (
    CONFIG_DIR,
    SETTINGS_FILE,
    _read_settings_file,
    load_raw_settings,
    read_settings_document_or_none,
    save_raw_settings,
)

DEFAULT_COLORS: dict[str, str] = {
    "bg_base": "#000000",
    "bg_elevated": "#000000",
    "bg_highlight": "#0a0a0a",
    "bg_card": "#0a0a0a",
    "bg_card_hover": "#121212",
    "accent": "#a855f7",
    "border": "#141414",
    "glass_fill": "#0a0a0a",
    "glass_border": "#141414",
    "glass_strong": "#0a0a0a",
    "text_primary": "#ffffff",
    "text_secondary": "#b3b3b3",
    "text_muted": "#737373",
    "text_on_accent": "#000000",
    "input_bg": "#0a0a0a",
    "input_border": "#141414",
    "slider_track": "#1a1a1a",
    "hover_overlay": "#141414",
    "card_bg": "#0a0a0a",
    "card_border": "#141414",
}

DEFAULT_UI: dict = {
    "window": {"custom_title_bar": True, "opacity": 1.0},
    "colors": deepcopy(DEFAULT_COLORS),
    "sidebar": {"width": 220, "visible": True},
    "search": {"width": 340, "placeholder": "Tìm trong thư viện…"},
    "player_bar": {"height": 108, "always_visible": False},
    "layout": {
        "grid_columns": 5,
        "content_padding": 24,
        "card_radius": 12,
        "card_gap": 2,
    },
}

_LEGACY_UI_FILE = CONFIG_DIR / "ui.json"
_LIMINAL_PREFIX = "liminal."
_COLOR_ALIASES: dict[str, str] = {
    "bgbase": "bg_base",
    "bgelevated": "bg_elevated",
    "bghighlight": "bg_highlight",
    "bgcard": "bg_card",
    "bgcardhover": "bg_card_hover",
    "glassfill": "glass_fill",
    "glassborder": "glass_border",
    "glassstrong": "glass_strong",
    "textprimary": "text_primary",
    "textsecondary": "text_secondary",
    "textmuted": "text_muted",
    "textonaccent": "text_on_accent",
    "inputbg": "input_bg",
    "inputborder": "input_border",
    "slidertrack": "slider_track",
    "hoveroverlay": "hover_overlay",
    "cardbg": "card_bg",
    "cardborder": "card_border",
}


def _deep_merge(base: dict, overlay: dict) -> dict:
    merged = deepcopy(base)
    for key, value in overlay.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _normalize_color(value: object, fallback: str) -> str:
    if not isinstance(value, str):
        return fallback
    text = value.strip()
    if len(text) == 7 and text.startswith("#"):
        return text
    if len(text) == 4 and text.startswith("#"):
        return f"#{text[1]}{text[1]}{text[2]}{text[2]}{text[3]}{text[3]}"
    return fallback


def _normalize_int(value: object, fallback: int, *, minimum: int = 0, maximum: int = 4096) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return fallback
    return max(minimum, min(maximum, number))


def _normalize_bool(value: object, fallback: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    return fallback


def _normalize_float(value: object, fallback: float, *, minimum: float = 0.0, maximum: float = 1.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return fallback
    return max(minimum, min(maximum, number))


def _camel_to_snake(name: str) -> str:
    text = re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
    return _COLOR_ALIASES.get(text.replace("_", ""), text)


def _normalize_color_key(key: str) -> str:
    normalized = _camel_to_snake(key.strip())
    if normalized in DEFAULT_COLORS:
        return normalized
    snake = key.strip().lower()
    return _COLOR_ALIASES.get(snake.replace("_", ""), snake)


def _set_nested(target: dict, path: list[str], value: object) -> None:
    if not path:
        return
    head = path[0]
    if len(path) == 1:
        target[head] = value
        return
    node = target.setdefault(head, {})
    if isinstance(node, dict):
        _set_nested(node, path[1:], value)


def _normalize_section_keys(section: dict, *, player_bar: bool = False) -> dict:
    mapped: dict = {}
    for key, value in section.items():
        snake = _camel_to_snake(key)
        if player_bar and snake == "always_visible":
            mapped["always_visible"] = value
        elif snake in {"width", "visible", "height", "placeholder", "always_visible"}:
            mapped[snake] = value
        elif snake in {"grid_columns", "content_padding", "card_radius", "card_gap"}:
            mapped[snake] = value
        elif snake == "custom_title_bar":
            mapped["custom_title_bar"] = value
        else:
            mapped[key] = value
    return mapped


def _normalize_liminal_block(block: dict) -> dict:
    result: dict = {}
    for key, value in block.items():
        snake = _camel_to_snake(key)
        if snake == "color_customizations" and isinstance(value, dict):
            colors = {
                _normalize_color_key(color_key): color_value
                for color_key, color_value in value.items()
            }
            result["colors"] = colors
            continue
        if snake in {"window", "sidebar", "search", "layout"} and isinstance(value, dict):
            result[snake] = _normalize_section_keys(value, player_bar=False)
            continue
        if snake == "player_bar" and isinstance(value, dict):
            result["player_bar"] = _normalize_section_keys(value, player_bar=True)
            continue
        if isinstance(value, dict):
            result[snake] = value
        else:
            result[snake] = value
    return result


def _collect_dotted_overrides(settings: dict) -> dict:
    overrides: dict = {}
    for key, value in settings.items():
        if not isinstance(key, str) or not key.startswith(_LIMINAL_PREFIX):
            continue
        path = [_camel_to_snake(part) for part in key[len(_LIMINAL_PREFIX):].split(".") if part]
        if not path:
            continue
        if path[0] == "color_customizations":
            if len(path) == 2:
                color_key = _normalize_color_key(path[1])
                overrides.setdefault("colors", {})[color_key] = value
            elif len(path) == 1 and isinstance(value, dict):
                overrides["colors"] = {
                    _normalize_color_key(k): v for k, v in value.items()
                }
            continue
        if path[0] == "player_bar" and len(path) == 2 and path[1] == "always_visible":
            overrides.setdefault("player_bar", {})["always_visible"] = value
            continue
        _set_nested(overrides, path, value)
    return overrides


def _collect_legacy_sections(settings: dict) -> dict:
    legacy: dict = {}
    for section in ("window", "sidebar", "search", "player_bar", "layout"):
        value = settings.get(section)
        if isinstance(value, dict):
            legacy[section] = _normalize_section_keys(value, player_bar=section == "player_bar")
    colors = settings.get("colors")
    if isinstance(colors, dict):
        legacy["colors"] = {
            _normalize_color_key(k): v for k, v in colors.items()
        }
    if "custom_title_bar" in settings:
        legacy.setdefault("window", {})["custom_title_bar"] = settings["custom_title_bar"]
    return legacy


def _migrate_legacy_ui_file(settings: dict) -> dict:
    if not _LEGACY_UI_FILE.exists():
        return settings
    try:
        legacy = json.loads(_LEGACY_UI_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return settings
    if not isinstance(legacy, dict):
        return settings

    merged = dict(settings)
    merged.setdefault("liminal", {})
    liminal_block = merged["liminal"]
    if not isinstance(liminal_block, dict):
        liminal_block = {}
        merged["liminal"] = liminal_block

    for section, value in legacy.items():
        if section == "version" or not isinstance(value, dict):
            continue
        if section == "colors":
            liminal_block.setdefault("colorCustomizations", {}).update(value)
        else:
            liminal_block.setdefault(section, {}).update(value)

    save_raw_settings(merged)
    try:
        _LEGACY_UI_FILE.unlink()
    except OSError:
        pass
    return merged


def resolve_ui_config(settings: dict | None = None) -> dict:
    """Merge defaults with VS Code-style settings overrides."""
    document = _migrate_legacy_ui_file(_read_settings_file()) if settings is None else settings
    overrides: dict = {}

    liminal = document.get("liminal")
    if isinstance(liminal, dict):
        overrides = _deep_merge(overrides, _normalize_liminal_block(liminal))

    overrides = _deep_merge(overrides, _collect_dotted_overrides(document))
    overrides = _deep_merge(overrides, _collect_legacy_sections(document))

    top_level_opacity = document.get("window_opacity") or document.get("windowOpacity")
    if top_level_opacity is not None:
        overrides.setdefault("window", {})["opacity"] = top_level_opacity

    return normalize_ui_config(overrides)


def normalize_ui_config(data: dict | None) -> dict:
    source = data if isinstance(data, dict) else {}
    merged = _deep_merge(DEFAULT_UI, source)

    colors = merged.setdefault("colors", {})
    for key, fallback in DEFAULT_COLORS.items():
        colors[key] = _normalize_color(colors.get(key), fallback)

    window = merged.setdefault("window", {})
    window["custom_title_bar"] = _normalize_bool(
        window.get("custom_title_bar"),
        DEFAULT_UI["window"]["custom_title_bar"],
    )
    window["opacity"] = _normalize_float(
        window.get("opacity"),
        DEFAULT_UI["window"]["opacity"],
        minimum=0.1,
        maximum=1.0,
    )

    sidebar = merged.setdefault("sidebar", {})
    sidebar["width"] = _normalize_int(sidebar.get("width"), DEFAULT_UI["sidebar"]["width"], minimum=160, maximum=480)
    sidebar["visible"] = _normalize_bool(sidebar.get("visible"), DEFAULT_UI["sidebar"]["visible"])

    search = merged.setdefault("search", {})
    search["width"] = _normalize_int(search.get("width"), DEFAULT_UI["search"]["width"], minimum=200, maximum=800)
    placeholder = search.get("placeholder")
    search["placeholder"] = (
        str(placeholder).strip()
        if isinstance(placeholder, str) and placeholder.strip()
        else DEFAULT_UI["search"]["placeholder"]
    )

    player_bar = merged.setdefault("player_bar", {})
    player_bar["height"] = _normalize_int(
        player_bar.get("height"),
        DEFAULT_UI["player_bar"]["height"],
        minimum=72,
        maximum=220,
    )
    player_bar["always_visible"] = _normalize_bool(
        player_bar.get("always_visible"),
        DEFAULT_UI["player_bar"]["always_visible"],
    )

    layout = merged.setdefault("layout", {})
    layout["grid_columns"] = _normalize_int(
        layout.get("grid_columns"), DEFAULT_UI["layout"]["grid_columns"], minimum=2, maximum=10
    )
    layout["content_padding"] = _normalize_int(
        layout.get("content_padding"), DEFAULT_UI["layout"]["content_padding"], minimum=8, maximum=64
    )
    layout["card_radius"] = _normalize_int(
        layout.get("card_radius"), DEFAULT_UI["layout"]["card_radius"], minimum=0, maximum=32
    )
    layout["card_gap"] = _normalize_int(
        layout.get("card_gap"), DEFAULT_UI["layout"]["card_gap"], minimum=2, maximum=48
    )
    return merged


def load_ui_config() -> dict:
    return resolve_ui_config()


def _try_read_settings_document() -> dict | None:
    return read_settings_document_or_none()


class UiConfigBridge(QObject):
    """Expose resolved UI settings to QML via context property `uiConfig`."""

    configChanged = pyqtSignal()
    settingsFileChanged = pyqtSignal()
    reloadStateChanged = pyqtSignal()
    autoReloadEnabledChanged = pyqtSignal()

    _RELOAD_DEBOUNCE_MS = 450
    _RELOAD_OK_CLEAR_MS = 4000

    def __init__(self, config: dict | None = None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._config = normalize_ui_config(config or load_ui_config())
        self._path = str(SETTINGS_FILE)
        self._auto_reload_enabled = _normalize_bool(
            load_raw_settings().get("auto_reload_enabled"),
            True,
        )
        if self._auto_reload_enabled:
            self._reload_state = "watching"
            self._reload_message = "Đang theo dõi thay đổi từ settings.json"
        else:
            self._reload_state = "disabled"
            self._reload_message = "Tự động áp dụng cấu hình đã tắt"

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(self._RELOAD_DEBOUNCE_MS)
        self._debounce.timeout.connect(self._reload_from_disk)

        self._ok_clear = QTimer(self)
        self._ok_clear.setSingleShot(True)
        self._ok_clear.setInterval(self._RELOAD_OK_CLEAR_MS)
        self._ok_clear.timeout.connect(self._clear_reload_ok)

        self._watcher = QFileSystemWatcher(self)
        self._watcher.fileChanged.connect(self._schedule_reload)
        self._watcher.directoryChanged.connect(self._on_directory_changed)
        self._ensure_watching()

    def _ensure_watching(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        config_path = str(SETTINGS_FILE)
        if SETTINGS_FILE.exists() and config_path not in self._watcher.files():
            self._watcher.addPath(config_path)
        config_dir = str(CONFIG_DIR)
        if config_dir not in self._watcher.directories():
            self._watcher.addPath(config_dir)

    def _on_directory_changed(self, _path: str) -> None:
        self._ensure_watching()
        self._schedule_reload(str(SETTINGS_FILE))

    def _schedule_reload(self, _path: str = "") -> None:
        if not self._auto_reload_enabled:
            return
        self._ensure_watching()
        self._debounce.start()

    def _set_reload_state(self, state: str, message: str) -> None:
        if self._reload_state == state and self._reload_message == message:
            return
        self._reload_state = state
        self._reload_message = message
        self.reloadStateChanged.emit()

    def _clear_reload_ok(self) -> None:
        if self._reload_state == "ok":
            self._set_reload_state("watching", "Đang theo dõi thay đổi từ settings.json")

    def _reload_from_disk(self) -> None:
        document = _try_read_settings_document()
        if document is None:
            self._set_reload_state("error", "Không thể đọc settings.json. Vui lòng kiểm tra cú pháp JSON.")
            return

        self._set_reload_state("reloading", "Đang áp dụng cấu hình giao diện…")
        try:
            new_config = normalize_ui_config(resolve_ui_config(document))
        except Exception as exc:
            self._set_reload_state("error", f"Cấu hình không hợp lệ: {exc}")
            return

        if new_config == self._config:
            self._set_reload_state("watching", "Đang theo dõi thay đổi từ settings.json")
            self.settingsFileChanged.emit()
            return

        self._config = new_config
        self.configChanged.emit()
        self.settingsFileChanged.emit()
        self._ok_clear.stop()
        self._set_reload_state("ok", "Đã áp dụng cấu hình thành công")
        self._ok_clear.start()

    def get_config(self) -> dict:
        return self._config

    @pyqtProperty(str, constant=True)
    def configPath(self) -> str:
        return self._path

    @pyqtProperty(str, notify=reloadStateChanged)
    def reloadState(self) -> str:
        return self._reload_state

    @pyqtProperty(str, notify=reloadStateChanged)
    def reloadMessage(self) -> str:
        return self._reload_message

    @pyqtProperty(bool, notify=autoReloadEnabledChanged)
    def autoReloadEnabled(self) -> bool:
        return self._auto_reload_enabled

    @pyqtSlot(bool)
    def setAutoReloadEnabled(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if self._auto_reload_enabled == enabled:
            return
        self._auto_reload_enabled = enabled
        save_raw_settings({"auto_reload_enabled": enabled})
        self.autoReloadEnabledChanged.emit()
        if enabled:
            self._set_reload_state("watching", "Đang theo dõi thay đổi từ settings.json")
            self._schedule_reload()
        else:
            self._debounce.stop()
            self._ok_clear.stop()
            self._set_reload_state("disabled", "Tự động áp dụng cấu hình đã tắt")

    def _color(self, key: str) -> str:
        return self._config["colors"][key]

    @pyqtProperty(str, notify=configChanged)
    def bgBase(self) -> str:
        return self._color("bg_base")

    @pyqtProperty(str, notify=configChanged)
    def bgElevated(self) -> str:
        return self._color("bg_elevated")

    @pyqtProperty(str, notify=configChanged)
    def bgHighlight(self) -> str:
        return self._color("bg_highlight")

    @pyqtProperty(str, notify=configChanged)
    def bgCard(self) -> str:
        return self._color("bg_card")

    @pyqtProperty(str, notify=configChanged)
    def bgCardHover(self) -> str:
        return self._color("bg_card_hover")

    @pyqtProperty(str, notify=configChanged)
    def accent(self) -> str:
        return self._color("accent")

    @pyqtProperty(str, notify=configChanged)
    def border(self) -> str:
        return self._color("border")

    @pyqtProperty(str, notify=configChanged)
    def glassFill(self) -> str:
        return self._color("glass_fill")

    @pyqtProperty(str, notify=configChanged)
    def glassBorder(self) -> str:
        return self._color("glass_border")

    @pyqtProperty(str, notify=configChanged)
    def glassStrong(self) -> str:
        return self._color("glass_strong")

    @pyqtProperty(str, notify=configChanged)
    def textPrimary(self) -> str:
        return self._color("text_primary")

    @pyqtProperty(str, notify=configChanged)
    def textSecondary(self) -> str:
        return self._color("text_secondary")

    @pyqtProperty(str, notify=configChanged)
    def textMuted(self) -> str:
        return self._color("text_muted")

    @pyqtProperty(str, notify=configChanged)
    def textOnAccent(self) -> str:
        return self._color("text_on_accent")

    @pyqtProperty(str, notify=configChanged)
    def inputBg(self) -> str:
        return self._color("input_bg")

    @pyqtProperty(str, notify=configChanged)
    def inputBorder(self) -> str:
        return self._color("input_border")

    @pyqtProperty(str, notify=configChanged)
    def sliderTrack(self) -> str:
        return self._color("slider_track")

    @pyqtProperty(str, notify=configChanged)
    def hoverOverlay(self) -> str:
        return self._color("hover_overlay")

    @pyqtProperty(str, notify=configChanged)
    def cardBg(self) -> str:
        return self._color("card_bg")

    @pyqtProperty(str, notify=configChanged)
    def cardBorder(self) -> str:
        return self._color("card_border")

    @pyqtProperty(bool, notify=configChanged)
    def customTitleBar(self) -> bool:
        return bool(self._config["window"]["custom_title_bar"])

    @pyqtProperty(float, notify=configChanged)
    def windowOpacity(self) -> float:
        return float(self._config["window"]["opacity"])

    @pyqtProperty(int, notify=configChanged)
    def sidebarWidth(self) -> int:
        return int(self._config["sidebar"]["width"])

    @pyqtProperty(bool, notify=configChanged)
    def sidebarVisible(self) -> bool:
        return bool(self._config["sidebar"]["visible"])

    @pyqtProperty(int, notify=configChanged)
    def searchWidth(self) -> int:
        return int(self._config["search"]["width"])

    @pyqtProperty(str, notify=configChanged)
    def searchPlaceholder(self) -> str:
        return str(self._config["search"]["placeholder"])

    @pyqtProperty(int, notify=configChanged)
    def playerBarHeight(self) -> int:
        return int(self._config["player_bar"]["height"])

    @pyqtProperty(bool, notify=configChanged)
    def playerBarAlwaysVisible(self) -> bool:
        return bool(self._config["player_bar"]["always_visible"])

    @pyqtProperty(int, notify=configChanged)
    def gridColumns(self) -> int:
        return int(self._config["layout"]["grid_columns"])

    @pyqtProperty(int, notify=configChanged)
    def contentPadding(self) -> int:
        return int(self._config["layout"]["content_padding"])

    @pyqtProperty(int, notify=configChanged)
    def cardRadius(self) -> int:
        return int(self._config["layout"]["card_radius"])

    @pyqtProperty(int, notify=configChanged)
    def cardGap(self) -> int:
        return int(self._config["layout"]["card_gap"])


def open_config_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(CONFIG_DIR)))
