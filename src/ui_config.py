"""Resolve UI appearance from ~/.config/liminal/settings.json (VS Code-style keys)."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path

from PyQt6.QtCore import QObject, QUrl, pyqtProperty
from PyQt6.QtGui import QDesktopServices

from src.settings_store import CONFIG_DIR, SETTINGS_FILE, _read_settings_file, save_raw_settings

DEFAULT_COLORS: dict[str, str] = {
    "bg_base": "#000000",
    "bg_elevated": "#121212",
    "bg_highlight": "#1a1a1a",
    "bg_card": "#181818",
    "bg_card_hover": "#282828",
    "accent": "#a855f7",
    "border": "#2a2a2a",
    "glass_fill": "#000000",
    "glass_border": "#2a2a2a",
    "glass_strong": "#1a1a1a",
    "text_primary": "#ffffff",
    "text_secondary": "#b3b3b3",
    "text_muted": "#6a6a6a",
    "text_on_accent": "#000000",
    "input_bg": "#1a1a1a",
    "input_border": "#2a2a2a",
    "slider_track": "#2a2a2a",
    "hover_overlay": "#282828",
    "card_bg": "#181818",
    "card_border": "#2a2a2a",
}

DEFAULT_UI: dict = {
    "window": {"custom_title_bar": False, "opacity": 1.0},
    "colors": deepcopy(DEFAULT_COLORS),
    "sidebar": {"width": 220, "visible": True},
    "search": {"width": 340, "placeholder": "Tìm trong thư viện…"},
    "player_bar": {"height": 108, "always_visible": False},
    "layout": {
        "grid_columns": 5,
        "content_padding": 24,
        "card_radius": 12,
        "card_gap": 20,
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
        layout.get("card_gap"), DEFAULT_UI["layout"]["card_gap"], minimum=4, maximum=48
    )
    return merged


def load_ui_config() -> dict:
    return resolve_ui_config()


class UiConfigBridge(QObject):
    """Expose resolved UI settings to QML via context property `uiConfig`."""

    def __init__(self, config: dict | None = None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._config = normalize_ui_config(config or load_ui_config())
        self._path = str(SETTINGS_FILE)

    @pyqtProperty(str, constant=True)
    def configPath(self) -> str:
        return self._path

    def _color(self, key: str) -> str:
        return self._config["colors"][key]

    @pyqtProperty(str, constant=True)
    def bgBase(self) -> str:
        return self._color("bg_base")

    @pyqtProperty(str, constant=True)
    def bgElevated(self) -> str:
        return self._color("bg_elevated")

    @pyqtProperty(str, constant=True)
    def bgHighlight(self) -> str:
        return self._color("bg_highlight")

    @pyqtProperty(str, constant=True)
    def bgCard(self) -> str:
        return self._color("bg_card")

    @pyqtProperty(str, constant=True)
    def bgCardHover(self) -> str:
        return self._color("bg_card_hover")

    @pyqtProperty(str, constant=True)
    def accent(self) -> str:
        return self._color("accent")

    @pyqtProperty(str, constant=True)
    def border(self) -> str:
        return self._color("border")

    @pyqtProperty(str, constant=True)
    def glassFill(self) -> str:
        return self._color("glass_fill")

    @pyqtProperty(str, constant=True)
    def glassBorder(self) -> str:
        return self._color("glass_border")

    @pyqtProperty(str, constant=True)
    def glassStrong(self) -> str:
        return self._color("glass_strong")

    @pyqtProperty(str, constant=True)
    def textPrimary(self) -> str:
        return self._color("text_primary")

    @pyqtProperty(str, constant=True)
    def textSecondary(self) -> str:
        return self._color("text_secondary")

    @pyqtProperty(str, constant=True)
    def textMuted(self) -> str:
        return self._color("text_muted")

    @pyqtProperty(str, constant=True)
    def textOnAccent(self) -> str:
        return self._color("text_on_accent")

    @pyqtProperty(str, constant=True)
    def inputBg(self) -> str:
        return self._color("input_bg")

    @pyqtProperty(str, constant=True)
    def inputBorder(self) -> str:
        return self._color("input_border")

    @pyqtProperty(str, constant=True)
    def sliderTrack(self) -> str:
        return self._color("slider_track")

    @pyqtProperty(str, constant=True)
    def hoverOverlay(self) -> str:
        return self._color("hover_overlay")

    @pyqtProperty(str, constant=True)
    def cardBg(self) -> str:
        return self._color("card_bg")

    @pyqtProperty(str, constant=True)
    def cardBorder(self) -> str:
        return self._color("card_border")

    @pyqtProperty(bool, constant=True)
    def customTitleBar(self) -> bool:
        return bool(self._config["window"]["custom_title_bar"])

    @pyqtProperty(float, constant=True)
    def windowOpacity(self) -> float:
        return float(self._config["window"]["opacity"])

    @pyqtProperty(int, constant=True)
    def sidebarWidth(self) -> int:
        return int(self._config["sidebar"]["width"])

    @pyqtProperty(bool, constant=True)
    def sidebarVisible(self) -> bool:
        return bool(self._config["sidebar"]["visible"])

    @pyqtProperty(int, constant=True)
    def searchWidth(self) -> int:
        return int(self._config["search"]["width"])

    @pyqtProperty(str, constant=True)
    def searchPlaceholder(self) -> str:
        return str(self._config["search"]["placeholder"])

    @pyqtProperty(int, constant=True)
    def playerBarHeight(self) -> int:
        return int(self._config["player_bar"]["height"])

    @pyqtProperty(bool, constant=True)
    def playerBarAlwaysVisible(self) -> bool:
        return bool(self._config["player_bar"]["always_visible"])

    @pyqtProperty(int, constant=True)
    def gridColumns(self) -> int:
        return int(self._config["layout"]["grid_columns"])

    @pyqtProperty(int, constant=True)
    def contentPadding(self) -> int:
        return int(self._config["layout"]["content_padding"])

    @pyqtProperty(int, constant=True)
    def cardRadius(self) -> int:
        return int(self._config["layout"]["card_radius"])

    @pyqtProperty(int, constant=True)
    def cardGap(self) -> int:
        return int(self._config["layout"]["card_gap"])


def open_config_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(CONFIG_DIR)))
