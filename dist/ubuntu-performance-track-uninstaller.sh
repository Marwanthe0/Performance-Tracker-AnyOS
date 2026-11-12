#!/usr/bin/env bash
# Standalone Uninstaller for Ubuntu Performance Track
# Removes all files, desktop shortcuts, autostart entries, and GNOME extensions.

echo "=================================================="
echo "    Uninstalling Ubuntu Performance Track         "
echo "=================================================="

# 1. Terminate running process
pkill -f "performance_track.app" 2>/dev/null || true

# 2. Check user-level install
USER_DIR="$HOME/.local/share/ubuntu-performance-track"
if [ -d "$USER_DIR" ]; then
    echo "--> Removing user installation from $USER_DIR..."
    rm -rf "$USER_DIR"
fi
rm -f "$HOME/.local/bin/ubuntu-performance-track"
rm -f "$HOME/.local/bin/ubuntu-performance-track-uninstall"
rm -f "$HOME/.local/share/applications/ubuntu-performance-track.desktop"
rm -f "$HOME/.config/autostart/ubuntu-performance-track.desktop"
rm -f "$HOME/.local/share/icons/hicolor/scalable/apps/performance-track.svg"
rm -f "$HOME/.local/share/icons/hicolor/scalable/apps/performance-track-symbolic.svg"
rm -rf "$HOME/.local/share/gnome-shell/extensions/performancetrack@ubuntu.local"

# 3. Check system-wide install if run with root
if [ "$EUID" -eq 0 ]; then
    echo "--> Removing system-wide installation..."
    rm -rf "/opt/ubuntu-performance-track"
    rm -f "/usr/local/bin/ubuntu-performance-track"
    rm -f "/usr/local/bin/ubuntu-performance-track-uninstall"
    rm -f "/usr/share/applications/ubuntu-performance-track.desktop"
    rm -f "/etc/xdg/autostart/ubuntu-performance-track.desktop"
    rm -f "/usr/share/icons/hicolor/scalable/apps/performance-track.svg"
    rm -f "/usr/share/icons/hicolor/scalable/apps/performance-track-symbolic.svg"
    rm -rf "/usr/share/gnome-shell/extensions/performancetrack@ubuntu.local"
fi

# 4. Clean caches
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
    if [ "$EUID" -eq 0 ]; then
        gtk-update-icon-cache -f -t "/usr/share/icons/hicolor" 2>/dev/null || true
    fi
fi

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
    if [ "$EUID" -eq 0 ]; then
        update-desktop-database "/usr/share/applications" 2>/dev/null || true
    fi
fi

echo "=================================================="
echo "    Uninstallation Complete!                     "
echo "=================================================="
