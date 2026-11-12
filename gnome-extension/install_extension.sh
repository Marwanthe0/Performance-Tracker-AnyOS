#!/usr/bin/env bash
# install_extension.sh - Installs and enables the GNOME Shell extension

UUID="performancetrack@ubuntu.local"
EXT_DIR="$HOME/.local/share/gnome-shell/extensions/$UUID"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"

echo "==> Installing GNOME Shell Extension ($UUID)..."
mkdir -p "$EXT_DIR"
cp -r "$SRC_DIR"/* "$EXT_DIR/"

echo "==> Enabling extension..."
gnome-extensions enable "$UUID" 2>/dev/null || true

echo "==> Extension installed to $EXT_DIR"
echo "Note: If running under Wayland, GNOME Shell discovers newly added extensions upon user login/session restart."
