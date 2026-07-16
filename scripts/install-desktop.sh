#!/usr/bin/env bash
# Install Liminal integration points: PATH wrapper, icon, and .desktop entry.
# The generated files contain NO hardcoded paths — safe to share or publish.
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# --- XDG paths ---
bin_dir="${HOME}/.local/bin"
apps_dir="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
icon_dir="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/scalable/apps"

mkdir -p "$bin_dir" "$apps_dir" "$icon_dir"

# 1. Install wrapper in ~/.local/bin so "liminal" is on PATH
wrapper="$bin_dir/liminal"
cat > "$wrapper" << WRAPPER
#!/usr/bin/env bash
exec "$root_dir/scripts/run-liminal.sh" "\$@"
WRAPPER
chmod +x "$wrapper"
echo "Installed: $wrapper"

# 2. Install icon to XDG icon theme path (so Icon=liminal resolves)
icon_src="$root_dir/src/qt/liminal.png"
if [[ -f "$icon_src" ]]; then
    cp "$icon_src" "$icon_dir/liminal.png"
    echo "Installed: $icon_dir/liminal.png"
else
    echo "Warning: icon not found at $icon_src" >&2
fi

# 3. Install .desktop entry (clean — no hardcoded paths)
desktop_src="$root_dir/liminal.desktop.in"
desktop_dst="$apps_dir/liminal.desktop"
if [[ -f "$desktop_src" ]]; then
    cp "$desktop_src" "$desktop_dst"
    chmod 644 "$desktop_dst"
    echo "Installed: $desktop_dst"
else
    echo "Missing: $desktop_src" >&2
    exit 1
fi

# 4. Ensure ~/.local/bin is on PATH
profile_line='export PATH="$HOME/.local/bin:$PATH"'
for rc in "$HOME/.bashrc" "$HOME/.profile" "$HOME/.zprofile"; do
    if [[ -f "$rc" ]] && ! grep -qF "$profile_line" "$rc"; then
        echo "$profile_line" >> "$rc"
        echo "Added ~/.local/bin to PATH in $rc"
    fi
done

echo ""
echo "Liminal installed. You may need to log out and back in for the icon to appear."
echo "Run from terminal: liminal"
