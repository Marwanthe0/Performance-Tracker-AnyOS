#!/usr/bin/env bash
# Standalone Uninstaller for Performance Track
echo "=================================================="
echo "    Uninstalling Performance Track                "
echo "=================================================="
pkill -f "performance_track.app" 2>/dev/null || true
USER_DIR="$HOME/.local/share/ubuntu-performance-track"
if [ -d "$USER_DIR" ]; then
    echo "--> Removing user installation from $USER_DIR..."
    rm -rf "$USER_DIR"
fi
rm -f "$HOME/.local/bin/ubuntu-performance-track"
rm -f "$HOME/.local/bin/performance-track"
rm -f "$HOME/.local/share/applications/ubuntu-performance-track.desktop"
rm -f "$HOME/.config/autostart/ubuntu-performance-track.desktop"
rm -f "$HOME/.config/autostart/performance-track.desktop"
echo "[OK] Uninstallation complete!"
