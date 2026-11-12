#!/usr/bin/env bash
# build_dist.sh - Builds downloadable installer packages for Ubuntu Performance Track:
# 1. Self-Extracting Installer: ubuntu-performance-track-installer.run
# 2. Standalone Uninstaller: ubuntu-performance-track-uninstaller.sh
# 3. Native Debian Package: ubuntu-performance-track_1.0.0_all.deb
# 4. Portable Source Tarball: ubuntu-performance-track-v1.0.0.tar.gz

set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
DIST_DIR="$DIR/dist"
BUILD_DIR="/tmp/upt_build_$$"

echo "=================================================="
echo " Building Distributable Installers..."
echo "=================================================="
mkdir -p "$DIST_DIR"
mkdir -p "$BUILD_DIR"
trap 'rm -rf "$BUILD_DIR"' EXIT

VERSION="1.0.0"

# ----------------------------------------------------
# 1. Build Portable Tarball (.tar.gz)
# ----------------------------------------------------
echo "--> [1/4] Building portable archive: ubuntu-performance-track-v1.0.0.tar.gz..."
TAR_CONTENT="$BUILD_DIR/ubuntu-performance-track"
mkdir -p "$TAR_CONTENT"
cp -r "$DIR/performance_track" "$TAR_CONTENT/"
cp -r "$DIR/gnome-extension" "$TAR_CONTENT/"
cp "$DIR/run.sh" "$TAR_CONTENT/"
cp "$DIR/install.sh" "$TAR_CONTENT/"
cp "$DIR/uninstall.sh" "$TAR_CONTENT/"
cp "$DIR/ubuntu-performance-track.desktop" "$TAR_CONTENT/"
cp "$DIR/README.md" "$TAR_CONTENT/"

# Clean any pycache in build content
find "$TAR_CONTENT" -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

tar -czf "$DIST_DIR/ubuntu-performance-track-v1.0.0.tar.gz" -C "$BUILD_DIR" ubuntu-performance-track

# ----------------------------------------------------
# 2. Build Self-Extracting Installer (.run)
# ----------------------------------------------------
echo "--> [2/4] Building self-extracting installer: ubuntu-performance-track-installer.run..."
RUN_FILE="$DIST_DIR/ubuntu-performance-track-installer.run"

cat << 'EOF' > "$RUN_FILE"
#!/usr/bin/env bash
# Ubuntu Performance Track - Self Extracting Installer
# This single file can be downloaded and run on any Ubuntu machine.

set -e

echo "=================================================="
echo "    Ubuntu Performance Track Installer            "
echo "=================================================="

TMP_DIR=$(mktemp -d /tmp/upt_setup_XXXXXX)
trap 'rm -rf "$TMP_DIR"' EXIT

ARCHIVE_LINE=$(awk '/^__ARCHIVE_PAYLOAD_BELOW__/ {print NR + 1; exit 0; }' "$0")

echo "--> Extracting installer files..."
tail -n +"$ARCHIVE_LINE" "$0" | tar -xz -C "$TMP_DIR"

# Execute internal installer
bash "$TMP_DIR/ubuntu-performance-track/install.sh" "$@"

exit 0

__ARCHIVE_PAYLOAD_BELOW__
EOF

cat "$DIST_DIR/ubuntu-performance-track-v1.0.0.tar.gz" >> "$RUN_FILE"
chmod +x "$RUN_FILE"

# ----------------------------------------------------
# 3. Create Standalone Uninstaller
# ----------------------------------------------------
echo "--> [3/4] Creating standalone uninstaller: ubuntu-performance-track-uninstaller.sh..."
UNINSTALL_FILE="$DIST_DIR/ubuntu-performance-track-uninstaller.sh"

cat << 'EOF' > "$UNINSTALL_FILE"
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
EOF
chmod +x "$UNINSTALL_FILE"

# ----------------------------------------------------
# 4. Build Native Debian Package (.deb)
# ----------------------------------------------------
echo "--> [4/4] Building Debian package: ubuntu-performance-track_1.0.0_all.deb..."
DEB_DIR="$BUILD_DIR/deb"
mkdir -p "$DEB_DIR/DEBIAN"
mkdir -p "$DEB_DIR/opt/ubuntu-performance-track"
mkdir -p "$DEB_DIR/usr/bin"
mkdir -p "$DEB_DIR/usr/share/applications"
mkdir -p "$DEB_DIR/usr/share/icons/hicolor/scalable/apps"
mkdir -p "$DEB_DIR/etc/xdg/autostart"
mkdir -p "$DEB_DIR/usr/share/gnome-shell/extensions/performancetrack@ubuntu.local"

# Copy app files
cp -r "$DIR/performance_track" "$DEB_DIR/opt/ubuntu-performance-track/"
cp -r "$DIR/gnome-extension" "$DEB_DIR/opt/ubuntu-performance-track/"
cp -r "$DIR/gnome-extension/"* "$DEB_DIR/usr/share/gnome-shell/extensions/performancetrack@ubuntu.local/"
cp "$DIR/performance_track/icons/performance-track.svg" "$DEB_DIR/usr/share/icons/hicolor/scalable/apps/"
cp "$DIR/performance_track/icons/performance-track-symbolic.svg" "$DEB_DIR/usr/share/icons/hicolor/scalable/apps/"

# Clean pycache
find "$DEB_DIR" -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# Runner script in /opt
cat << 'EOF' > "$DEB_DIR/opt/ubuntu-performance-track/run.sh"
#!/usr/bin/env bash
export PYTHONPATH="/opt/ubuntu-performance-track:$PYTHONPATH"
exec python3 -m performance_track.app "$@"
EOF
chmod +x "$DEB_DIR/opt/ubuntu-performance-track/run.sh"

# Launcher in /usr/bin
cat << 'EOF' > "$DEB_DIR/usr/bin/ubuntu-performance-track"
#!/usr/bin/env bash
exec /opt/ubuntu-performance-track/run.sh "$@"
EOF
chmod +x "$DEB_DIR/usr/bin/ubuntu-performance-track"

# Desktop entry
cat << 'EOF' > "$DEB_DIR/usr/share/applications/ubuntu-performance-track.desktop"
[Desktop Entry]
Version=1.0
Type=Application
Name=Ubuntu Performance Track
GenericName=System Performance Monitor
Comment=Real-time RAM, CPU, and Performance Tracking in the Ubuntu Topbar
Exec=ubuntu-performance-track
Icon=performance-track
Terminal=false
Categories=System;Monitor;Utility;
Keywords=system;cpu;ram;memory;disk;network;performance;track;monitor;topbar;
StartupNotify=true
Actions=Dashboard;

[Desktop Action Dashboard]
Name=Open Performance Track Dashboard
Exec=ubuntu-performance-track --dashboard
EOF

# Autostart
cp "$DEB_DIR/usr/share/applications/ubuntu-performance-track.desktop" "$DEB_DIR/etc/xdg/autostart/"

# Control file
cat << EOF > "$DEB_DIR/DEBIAN/control"
Package: ubuntu-performance-track
Version: $VERSION
Section: utils
Priority: optional
Architecture: all
Maintainer: Ubuntu Performance Track Team <support@ubuntu.com>
Depends: python3 (>= 3.8), python3-gi, gir1.2-gtk-3.0, libayatana-appindicator3-1
Description: Real-time RAM, CPU, and Performance Tracking in the Ubuntu Topbar
 A lightweight, feature-rich topbar system performance monitor for Ubuntu.
 Displays live CPU %, RAM %, and I/O Performance Track directly on the top panel,
 with rich dropdown breakdowns, per-core meters, and a GUI dashboard with Cairo graphs.
EOF

# Postinst script
cat << 'EOF' > "$DEB_DIR/DEBIAN/postinst"
#!/usr/bin/env bash
set -e
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t /usr/share/icons/hicolor 2>/dev/null || true
fi
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database /usr/share/applications 2>/dev/null || true
fi
exit 0
EOF
chmod 755 "$DEB_DIR/DEBIAN/postinst"

# Prerm script
cat << 'EOF' > "$DEB_DIR/DEBIAN/prerm"
#!/usr/bin/env bash
pkill -f "performance_track.app" 2>/dev/null || true
exit 0
EOF
chmod 755 "$DEB_DIR/DEBIAN/prerm"

# Postrm script
cat << 'EOF' > "$DEB_DIR/DEBIAN/postrm"
#!/usr/bin/env bash
set -e
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t /usr/share/icons/hicolor 2>/dev/null || true
fi
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database /usr/share/applications 2>/dev/null || true
fi
exit 0
EOF
chmod 755 "$DEB_DIR/DEBIAN/postrm"

dpkg-deb --build --root-owner-group "$DEB_DIR" "$DIST_DIR/ubuntu-performance-track_${VERSION}_all.deb"

echo "=================================================="
echo " Build Completed Successfully! Packages in $DIST_DIR:"
echo "=================================================="
ls -lh "$DIST_DIR"
