#!/usr/bin/env bash
# Start one Liminal instance per Linux user session.
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
runtime_dir="${XDG_RUNTIME_DIR:-${XDG_CACHE_HOME:-$HOME/.cache}}"
lock_dir="$runtime_dir/liminal"
lock_file="$lock_dir/app.lock"

mkdir -p "$lock_dir"
exec 9>"$lock_file"

# mpv --wid embedding is X11-only.  Ubuntu and Arch commonly start GNOME on
# Wayland, but expose XWayland as DISPLAY; using Qt's xcb backend in that case
# preserves the in-app focus player.  Respect an explicit user choice and
# leave pure Wayland sessions untouched (PlayerBridge then falls back to a
# managed mpv window instead of passing an invalid WId).
if [[ -z "${QT_QPA_PLATFORM:-}" && -n "${WAYLAND_DISPLAY:-}" && -n "${DISPLAY:-}" ]]; then
    export QT_QPA_PLATFORM=xcb
fi

if ! flock -n 9; then
    if command -v notify-send >/dev/null 2>&1; then
        notify-send "Liminal" "Liminal đang chạy."
    fi
    exit 0
fi

# Auto-detect virtual environment
if [ -f "$root_dir/.venv/bin/python3" ]; then
    PYTHON="$root_dir/.venv/bin/python3"
elif [ -f "$root_dir/.venv/bin/python" ]; then
    PYTHON="$root_dir/.venv/bin/python"
elif [ -f "$root_dir/venv/bin/python3" ]; then
    PYTHON="$root_dir/venv/bin/python3"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON="python3"
else
    PYTHON="python"
fi

exec "$PYTHON" "$root_dir/app_qt.py"
