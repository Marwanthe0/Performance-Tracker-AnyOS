#!/usr/bin/env bash
# build_macos.sh - Build macOS Application Bundle (.app) and ZIP Archive
set -e
echo "=================================================="
echo " Building Performance Track for macOS...          "
echo "=================================================="

python3 -m pip install --upgrade pyinstaller psutil pystray pillow
python3 build.py --target macos
echo "[OK] macOS build completed!"
