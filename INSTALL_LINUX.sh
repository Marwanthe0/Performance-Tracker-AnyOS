#!/usr/bin/env bash
# PC Performance Tracker - 1-Click Linux Installer
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "=================================================="
echo "    PC Performance Tracker - Linux Installer      "
echo "=================================================="

# Check if native Debian/Ubuntu .deb package exists
if [ -f "$DIR/Installers/Linux/ubuntu-performance-track_1.0.0_all.deb" ] && command -v apt >/dev/null 2>&1; then
    echo "[*] Detected Debian/Ubuntu environment."
    echo "[*] Installing native .deb package..."
    sudo apt install -y "$DIR/Installers/Linux/ubuntu-performance-track_1.0.0_all.deb" || sudo dpkg -i "$DIR/Installers/Linux/ubuntu-performance-track_1.0.0_all.deb"
    echo ""
    echo "[OK] Installed successfully! Launch from Application Menu or run 'ubuntu-performance-track'."
    exit 0
fi

# Fallback to self-extracting .run package
if [ -f "$DIR/Installers/Linux/ubuntu-performance-track-installer.run" ]; then
    echo "[*] Launching standalone installer..."
    bash "$DIR/Installers/Linux/ubuntu-performance-track-installer.run"
    exit 0
fi

# Fallback to install.sh
if [ -f "$DIR/install.sh" ]; then
    bash "$DIR/install.sh"
    exit 0
fi

echo "[!] Error: No Linux installer package found."
exit 1
