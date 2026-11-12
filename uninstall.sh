#!/usr/bin/env bash
# uninstall.sh - Clean uninstaller for Ubuntu Performance Track

BIN_DIR="$HOME/.local/bin"
ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"
APP_DESKTOP_DIR="$HOME/.local/share/applications"
AUTOSTART_DIR="$HOME/.config/autostart"
EXT_DIR="$HOME/.local/share/gnome-shell/extensions/performancetrack@ubuntu.local"

echo "=========================================="
echo " Uninstalling Ubuntu Performance Track"
echo "=========================================="

# Stop running instances
pkill -f "performance_track.app" 2>/dev/null || true

# Remove binaries and desktop files
rm -f "$BIN_DIR/ubuntu-performance-track"
rm -f "$APP_DESKTOP_DIR/ubuntu-performance-track.desktop"
rm -f "$AUTOSTART_DIR/ubuntu-performance-track.desktop"
rm -f "$ICON_DIR/performance-track.svg"
rm -f "$ICON_DIR/performance-track-symbolic.svg"
rm -rf "$EXT_DIR"

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
fi
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APP_DESKTOP_DIR" 2>/dev/null || true
fi

echo "Uninstalled successfully."
