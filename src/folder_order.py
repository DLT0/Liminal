"""Persist custom item order inside library folders."""

from __future__ import annotations

import json
from pathlib import Path

ORDER_FILENAME = ".liminal-order.json"


def _order_path(folder: Path) -> Path:
    return folder / ORDER_FILENAME


def read_order(folder: Path) -> list[str] | None:
    """Return stored basename order for *folder*, or None if missing."""
    path = _order_path(folder)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        order = data.get("order")
        if isinstance(order, list):
            return [str(name) for name in order]
    except (OSError, json.JSONDecodeError):
        return None
    return None


def write_order(folder: Path, names: list[str]) -> None:
    """Persist basename order for children of *folder*."""
    folder.mkdir(parents=True, exist_ok=True)
    _order_path(folder).write_text(
        json.dumps({"order": names}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def apply_order[T](items: list[T], folder: Path, *, key) -> list[T]:
    """Sort *items* using stored order; unknown items append alphabetically."""
    order = read_order(folder)
    if not order:
        return items

    by_name = {key(item): item for item in items}
    ordered: list[T] = []
    seen: set[str] = set()

    for name in order:
        item = by_name.get(name)
        if item is not None:
            ordered.append(item)
            seen.add(name)

    remaining = sorted(
        (item for item in items if key(item) not in seen),
        key=key,
    )
    ordered.extend(remaining)
    return ordered
