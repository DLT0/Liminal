"""Persistent device identity for media share (Phase 1 — no GitHub OAuth)."""

from __future__ import annotations

import json
import uuid

from src.settings_store import CONFIG_DIR

DEVICE_FILE = CONFIG_DIR / "device.json"


def get_device_id() -> str:
    """Return a stable UUID for this installation."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if DEVICE_FILE.exists():
        try:
            data = json.loads(DEVICE_FILE.read_text(encoding="utf-8"))
            value = str(data.get("device_id") or "").strip()
            if value:
                return value
        except (OSError, json.JSONDecodeError):
            pass

    device_id = str(uuid.uuid4())
    DEVICE_FILE.write_text(
        json.dumps({"device_id": device_id}, indent=2) + "\n",
        encoding="utf-8",
    )
    return device_id
