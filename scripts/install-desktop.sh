#!/usr/bin/env bash
# Generate and install a user-local .desktop entry with the correct project paths.
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
template="$root_dir/liminal.desktop.in"
dest_dir="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
dest_file="$dest_dir/liminal.desktop"

if [[ ! -f "$template" ]]; then
    echo "Missing template: $template" >&2
    exit 1
fi

mkdir -p "$dest_dir"
sed "s|@PROJECT_ROOT@|$root_dir|g" "$template" > "$dest_file"
chmod +x "$root_dir/scripts/run-liminal.sh"
chmod 644 "$dest_file"

echo "Installed desktop entry: $dest_file"
