#!/usr/bin/env bash
# Start one Liminal instance per Linux user session.
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
runtime_dir="${XDG_RUNTIME_DIR:-${XDG_CACHE_HOME:-$HOME/.cache}}"
lock_dir="$runtime_dir/liminal"
lock_file="$lock_dir/app.lock"

mkdir -p "$lock_dir"
exec 9>"$lock_file"

if ! flock -n 9; then
    if command -v notify-send >/dev/null 2>&1; then
        notify-send "Liminal" "Liminal đang chạy."
    fi
    exit 0
fi

exec python3 "$root_dir/app_qt.py"
