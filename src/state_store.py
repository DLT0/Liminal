"""Runtime session state — separate from user-editable settings.json."""

from __future__ import annotations

import json

from src.settings_store import CONFIG_DIR, SETTINGS_FILE, _ensure_config_dir, _read_settings_file

STATE_FILE = CONFIG_DIR / "state.json"
STATE_VERSION = 1

SESSION_KEYS = (
    "has_played_before",
    "last_track_title",
    "last_track_artist",
    "last_track_thumbnail",
    "last_track_path",
    "last_track_audio_only",
    "last_track_position",
)

STATE_DEFAULTS: dict = {
    "version": STATE_VERSION,
    "has_played_before": False,
    "last_track_title": "",
    "last_track_artist": "",
    "last_track_thumbnail": "",
    "last_track_path": "",
    "last_track_audio_only": True,
    "last_track_position": 0.0,
}


def _read_state_file() -> dict:
    if not STATE_FILE.exists():
        return {}
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_state_file(data: dict) -> None:
    _ensure_config_dir()
    STATE_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def migrate_state_from_settings() -> None:
    """Move legacy session keys out of settings.json into state.json."""
    settings = _read_settings_file()
    if not any(key in settings for key in SESSION_KEYS):
        return

    state = _read_state_file()
    for key in SESSION_KEYS:
        if key in settings:
            state[key] = settings[key]

    state["version"] = STATE_VERSION
    _write_state_file(state)

    cleaned = {k: v for k, v in settings.items() if k not in SESSION_KEYS}
    cleaned["version"] = settings.get("version", 6)
    _ensure_config_dir()
    SETTINGS_FILE.write_text(
        json.dumps(cleaned, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def load_raw_state() -> dict:
    migrate_state_from_settings()
    data = _read_state_file()
    merged = dict(STATE_DEFAULTS)
    merged.update({k: v for k, v in data.items() if k in merged or k == "version"})
    merged["version"] = STATE_VERSION
    return merged


def save_raw_state(data: dict) -> None:
    current = _read_state_file()
    current.update(data)
    current["version"] = STATE_VERSION
    _write_state_file(current)
