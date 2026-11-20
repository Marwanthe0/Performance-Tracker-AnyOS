#!/usr/bin/env bash
# PC Performance Tracker - macOS 1-Click Installer
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=================================================="
echo "    PC Performance Tracker - macOS Installer      "
echo "=================================================="

# Check Python 3
if ! command -v python3 >/dev/null 2>&1; then
    echo "[!] Python 3 is required. Please install Python 3 via https://python.org or 'brew install python'"
    exit 1
fi

echo "[*] Installing required dependencies..."
python3 -m pip install --upgrade psutil pystray pillow --quiet

TARGET_DIR="$HOME/Applications/PerformanceTracker"
mkdir -p "$TARGET_DIR"

echo "[*] Installing application files to $TARGET_DIR..."
cp -R "$DIR/../../performance_track" "$TARGET_DIR/" 2>/dev/null || cp -R "$DIR/../performance_track" "$TARGET_DIR/" 2>/dev/null || true

# Create command line launcher in ~/.local/bin or /usr/local/bin
LAUNCHER="$HOME/.local/bin/performance-tracker"
mkdir -p "$HOME/.local/bin"
cat << 'EOF' > "$LAUNCHER"
#!/usr/bin/env bash
APP_DIR="$HOME/Applications/PerformanceTracker"
exec python3 -m performance_track.app "$@"
EOF
chmod +x "$LAUNCHER"

echo.
echo "=================================================="
echo "  [OK] Installation completed successfully!"
echo "=================================================="
echo "You can launch PC Performance Tracker with:"
echo "  $HOME/.local/bin/performance-tracker"
echo ""
echo "[*] Launching now..."
python3 -m performance_track.app &
