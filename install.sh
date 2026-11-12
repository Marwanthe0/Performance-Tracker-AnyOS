#!/usr/bin/env bash
# install.sh - Universal installer for Ubuntu Performance Track
# Supports both user-level installation (default, no root needed) and system-wide (--system)

set -e

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
SYSTEM_INSTALL=false

for arg in "$@"; do
    case $arg in
        --system)
            SYSTEM_INSTALL=true
            shift
            ;;
        -h|--help)
            echo "Usage: ./install.sh [--system]"
            echo "  (default): Installs into ~/.local/ without root privileges"
            echo "  --system:  Installs into /opt/ and /usr/local/bin (requires sudo)"
            exit 0
            ;;
    esac
done

if [ "$SYSTEM_INSTALL" = true ]; then
    if [ "$EUID" -ne 0 ]; then
        echo "[!] Error: --system installation requires root privileges. Please run with sudo."
        exit 1
    fi
    INSTALL_DIR="/opt/ubuntu-performance-track"
    BIN_DIR="/usr/local/bin"
    ICON_DIR="/usr/share/icons/hicolor/scalable/apps"
    DESKTOP_DIR="/usr/share/applications"
    AUTOSTART_DIR="/etc/xdg/autostart"
else
    INSTALL_DIR="$HOME/.local/share/ubuntu-performance-track"
    BIN_DIR="$HOME/.local/bin"
    ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"
    DESKTOP_DIR="$HOME/.local/share/applications"
    AUTOSTART_DIR="$HOME/.config/autostart"
fi

echo "=================================================="
echo "    Installing Ubuntu Performance Track           "
echo "=================================================="
echo "Destination: $INSTALL_DIR"

# 1. Stop any running instances first
pkill -f "performance_track.app" 2>/dev/null || true

# 2. Create destination directories
mkdir -p "$INSTALL_DIR"
mkdir -p "$BIN_DIR"
mkdir -p "$ICON_DIR"
mkdir -p "$DESKTOP_DIR"
mkdir -p "$AUTOSTART_DIR"

# 3. Copy application files
echo "--> Copying application files..."
cp -r "$SRC_DIR/performance_track" "$INSTALL_DIR/"
cp -r "$SRC_DIR/gnome-extension" "$INSTALL_DIR/"

# Create runner script inside INSTALL_DIR
cat << 'EOF' > "$INSTALL_DIR/run.sh"
#!/usr/bin/env bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
export PYTHONPATH="$DIR:$PYTHONPATH"
exec python3 -m performance_track.app "$@"
EOF
chmod +x "$INSTALL_DIR/run.sh"

# 4. Create launcher in BIN_DIR
echo "--> Installing command launcher: $BIN_DIR/ubuntu-performance-track..."
cat << EOF > "$BIN_DIR/ubuntu-performance-track"
#!/usr/bin/env bash
exec "$INSTALL_DIR/run.sh" "\$@"
EOF
chmod +x "$BIN_DIR/ubuntu-performance-track"

# 5. Install Icons
echo "--> Installing application icons..."
cp "$SRC_DIR/performance_track/icons/performance-track.svg" "$ICON_DIR/"
cp "$SRC_DIR/performance_track/icons/performance-track-symbolic.svg" "$ICON_DIR/"
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "$(dirname "$ICON_DIR")" 2>/dev/null || true
fi

# 6. Install Desktop Entry
echo "--> Registering application shortcut..."
cat << EOF > "$DESKTOP_DIR/ubuntu-performance-track.desktop"
[Desktop Entry]
Version=1.0
Type=Application
Name=Ubuntu Performance Track
GenericName=System Performance Monitor
Comment=Real-time RAM, CPU, and Performance Tracking in the Ubuntu Topbar
Exec=$BIN_DIR/ubuntu-performance-track
Icon=performance-track
Terminal=false
Categories=System;Monitor;Utility;
Keywords=system;cpu;ram;memory;disk;network;performance;track;monitor;topbar;
StartupNotify=true
Actions=Dashboard;

[Desktop Action Dashboard]
Name=Open Performance Track Dashboard
Exec=$BIN_DIR/ubuntu-performance-track --dashboard
EOF

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
fi

# 7. Setup Autostart on Ubuntu Login
echo "--> Setting up autostart..."
cp "$DESKTOP_DIR/ubuntu-performance-track.desktop" "$AUTOSTART_DIR/"

# 8. Install GNOME Shell Extension
if [ "$SYSTEM_INSTALL" = true ]; then
    SYS_EXT_DIR="/usr/share/gnome-shell/extensions/performancetrack@ubuntu.local"
    mkdir -p "$SYS_EXT_DIR"
    cp -r "$SRC_DIR/gnome-extension/"* "$SYS_EXT_DIR/"
else
    USER_EXT_DIR="$HOME/.local/share/gnome-shell/extensions/performancetrack@ubuntu.local"
    mkdir -p "$USER_EXT_DIR"
    cp -r "$SRC_DIR/gnome-extension/"* "$USER_EXT_DIR/"
    if command -v gnome-extensions >/dev/null 2>&1; then
        gnome-extensions enable performancetrack@ubuntu.local 2>/dev/null || true
    fi
fi

# 9. Create dedicated Uninstaller script
echo "--> Creating uninstaller script..."
cat << EOF > "$INSTALL_DIR/uninstall.sh"
#!/usr/bin/env bash
# Uninstaller for Ubuntu Performance Track

set -e
SYSTEM_INSTALL=$SYSTEM_INSTALL

echo "=================================================="
echo "    Uninstalling Ubuntu Performance Track         "
echo "=================================================="

# 1. Stop running instances
pkill -f "performance_track.app" 2>/dev/null || true

# 2. Remove binaries and desktop files
rm -f "$BIN_DIR/ubuntu-performance-track"
rm -f "$BIN_DIR/ubuntu-performance-track-uninstall"
rm -f "$DESKTOP_DIR/ubuntu-performance-track.desktop"
rm -f "$AUTOSTART_DIR/ubuntu-performance-track.desktop"
rm -f "$ICON_DIR/performance-track.svg"
rm -f "$ICON_DIR/performance-track-symbolic.svg"

# 3. Remove GNOME Extension
if [ "\$SYSTEM_INSTALL" = true ]; then
    rm -rf "/usr/share/gnome-shell/extensions/performancetrack@ubuntu.local"
else
    rm -rf "\$HOME/.local/share/gnome-shell/extensions/performancetrack@ubuntu.local"
fi

# 4. Remove installation directory
rm -rf "$INSTALL_DIR"

# 5. Clean caches
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "\$(dirname "$ICON_DIR")" 2>/dev/null || true
fi
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
fi

echo "--> Ubuntu Performance Track has been cleanly uninstalled."
EOF
chmod +x "$INSTALL_DIR/uninstall.sh"

# Link uninstaller to BIN_DIR
cat << EOF > "$BIN_DIR/ubuntu-performance-track-uninstall"
#!/usr/bin/env bash
exec "$INSTALL_DIR/uninstall.sh" "\$@"
EOF
chmod +x "$BIN_DIR/ubuntu-performance-track-uninstall"

# Copy uninstaller to current directory if not already there
cp "$INSTALL_DIR/uninstall.sh" "$SRC_DIR/uninstall.sh" 2>/dev/null || true

# 10. Launch in background
if [ "$SYSTEM_INSTALL" = false ] && [ -n "$DISPLAY$WAYLAND_DISPLAY" ]; then
    echo "--> Launching Ubuntu Performance Track on topbar..."
    nohup "$BIN_DIR/ubuntu-performance-track" >/dev/null 2>&1 &
fi

echo "=================================================="
echo "    Installation Successful!                      "
echo "=================================================="
echo "The topbar monitor is now active."
echo "Commands:"
echo "  • Open Dashboard:       ubuntu-performance-track --dashboard"
echo "  • Launch on Topbar:     ubuntu-performance-track"
echo "  • Uninstall anytime:    ubuntu-performance-track-uninstall"
echo "                          or run: $INSTALL_DIR/uninstall.sh"
echo "=================================================="
