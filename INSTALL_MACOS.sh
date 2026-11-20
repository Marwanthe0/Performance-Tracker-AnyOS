#!/usr/bin/env bash
# PC Performance Tracker - 1-Click macOS Installer
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "=================================================="
echo "    PC Performance Tracker - macOS Installer      "
echo "=================================================="

if [ -f "$DIR/Installers/macOS/Install-macOS.sh" ]; then
    bash "$DIR/Installers/macOS/Install-macOS.sh"
    exit 0
fi

if [ -f "$DIR/Installers/macOS/PerformanceTracker-macOS.zip" ]; then
    echo "[*] Extracting PerformanceTracker to /Applications..."
    unzip -q -o "$DIR/Installers/macOS/PerformanceTracker-macOS.zip" -d /Applications/ 2>/dev/null || unzip -q -o "$DIR/Installers/macOS/PerformanceTracker-macOS.zip" -d "$HOME/Applications/"
    echo "[OK] Installed to Applications!"
    exit 0
fi

echo "[*] Installing Python dependencies..."
python3 -m pip install --upgrade psutil pystray pillow --quiet
python3 -m performance_track.app &
