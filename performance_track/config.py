"""
config.py - Persistent configuration manager for Performance Track.
Cross-platform support for Windows, macOS, and Linux.
Handles config JSON persistence and platform-native autostart configuration.
"""

import os
import sys
import json
import logging
import platform

SYS_NAME = platform.system()

# Determine standard OS configuration directory
if SYS_NAME == "Windows":
    _app_data = os.environ.get("APPDATA") or os.path.expanduser("~")
    CONFIG_DIR = os.path.join(_app_data, "PerformanceTrack")
elif SYS_NAME == "Darwin":
    CONFIG_DIR = os.path.expanduser("~/Library/Application Support/PerformanceTrack")
else:
    # Linux & other UNIX
    CONFIG_DIR = os.path.expanduser("~/.config/performance-track")
    # Legacy fallback
    if not os.path.isdir(CONFIG_DIR) and os.path.isdir(os.path.expanduser("~/.config/ubuntu-performance-track")):
        CONFIG_DIR = os.path.expanduser("~/.config/ubuntu-performance-track")

CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

# Linux autostart desktop path
LINUX_AUTOSTART_DIR = os.path.expanduser("~/.config/autostart")
LINUX_AUTOSTART_FILE = os.path.join(LINUX_AUTOSTART_DIR, "performance-track.desktop")

# macOS launchd agent path
MAC_LAUNCH_AGENTS_DIR = os.path.expanduser("~/Library/LaunchAgents")
MAC_PLIST_FILE = os.path.join(MAC_LAUNCH_AGENTS_DIR, "com.performancetrack.app.plist")

# Windows startup directory path
WIN_STARTUP_DIR = (
    os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs\Startup")
    if SYS_NAME == "Windows" else ""
)
WIN_STARTUP_FILE = os.path.join(WIN_STARTUP_DIR, "PerformanceTrack.bat") if WIN_STARTUP_DIR else ""

DEFAULT_CONFIG = {
    "update_interval": 1.0,
    "display_mode": "balanced",       # "balanced", "sparkline", "compact", "minimal", "detailed"
    "show_desktop_bar": True,         # Always-on-screen Floating Top/Bottom status bar
    "bar_position": "top",            # "top", "bottom", or "custom"
    "bar_x": None,
    "bar_y": None,
    "bar_opacity": 0.95,
    "show_cpu": True,
    "show_ram": True,
    "show_track": True,
    "show_sparklines": True,
    "track_metric": "network",        # "network", "disk", "both"
    "history_size": 60,
    "autostart": False
}


class Config:
    def __init__(self):
        self.data = dict(DEFAULT_CONFIG)
        self.load()

    def get(self, key, default=None):
        return self.data.get(key, default if default is not None else DEFAULT_CONFIG.get(key))

    def set(self, key, value):
        self.data[key] = value
        self.save()

    def load(self):
        if os.path.isfile(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, dict):
                        self.data.update(loaded)
            except Exception as e:
                logging.warning(f"Could not load config file {CONFIG_FILE}: {e}")
        else:
            self.save()

    def save(self):
        saved = False
        for target_dir, target_file in [
            (CONFIG_DIR, CONFIG_FILE),
            (os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".config")),
             os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".config", "config.json")))
        ]:
            try:
                os.makedirs(target_dir, exist_ok=True)
                with open(target_file, "w", encoding="utf-8") as f:
                    json.dump(self.data, f, indent=2)
                saved = True
                break
            except Exception:
                continue

        if not saved:
            logging.debug(f"Could not persist config to disk (read-only mode active).")

    def sync_autostart(self, exec_path=None):
        """Enable or disable autostart based on current config."""
        autostart_enabled = self.get("autostart", False)
        if autostart_enabled:
            self.enable_autostart(exec_path)
        else:
            self.disable_autostart()

    def _resolve_executable(self, exec_path=None):
        if exec_path and os.path.exists(exec_path):
            return os.path.abspath(exec_path)

        # Check if running bundled via PyInstaller
        if getattr(sys, "frozen", False):
            return sys.executable

        # Check standard Linux locations
        linux_user_bin = os.path.expanduser("~/.local/bin/ubuntu-performance-track")
        if os.path.exists(linux_user_bin):
            return linux_user_bin

        # Default to sys.executable with run launcher
        script_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        if SYS_NAME == "Windows":
            bat_run = os.path.join(script_dir, "run.bat")
            if os.path.exists(bat_run):
                return bat_run
        else:
            sh_run = os.path.join(script_dir, "run.sh")
            if os.path.exists(sh_run):
                return sh_run

        return f'"{sys.executable}" "{os.path.join(script_dir, "performance_track", "app.py")}"'

    def enable_autostart(self, exec_path=None):
        target = self._resolve_executable(exec_path)

        if SYS_NAME == "Windows":
            try:
                if WIN_STARTUP_DIR:
                    os.makedirs(WIN_STARTUP_DIR, exist_ok=True)
                    with open(WIN_STARTUP_FILE, "w", encoding="utf-8") as f:
                        f.write(f'@echo off\r\nstart "" {target}\r\n')
                self.data["autostart"] = True
                self.save()
            except Exception as e:
                logging.error(f"Failed to enable Windows autostart: {e}")

        elif SYS_NAME == "Darwin":
            try:
                os.makedirs(MAC_LAUNCH_AGENTS_DIR, exist_ok=True)
                plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.performancetrack.app</string>
    <key>ProgramArguments</key>
    <array>
        <string>{target}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
"""
                with open(MAC_PLIST_FILE, "w", encoding="utf-8") as f:
                    f.write(plist_content)
                self.data["autostart"] = True
                self.save()
            except Exception as e:
                logging.error(f"Failed to enable macOS autostart: {e}")

        else:
            # Linux XDG Autostart
            try:
                os.makedirs(LINUX_AUTOSTART_DIR, exist_ok=True)
                content = f"""[Desktop Entry]
Type=Application
Name=Performance Track
Comment=Live RAM, CPU, and Performance Tracking in Topbar
Exec={target}
Icon=utilities-system-monitor
Terminal=false
Categories=System;Monitor;Utility;
StartupNotify=false
X-GNOME-Autostart-enabled=true
"""
                with open(LINUX_AUTOSTART_FILE, "w", encoding="utf-8") as f:
                    f.write(content)
                self.data["autostart"] = True
                self.save()
            except Exception as e:
                logging.error(f"Failed to write autostart desktop file: {e}")

    def disable_autostart(self):
        try:
            if SYS_NAME == "Windows":
                if WIN_STARTUP_FILE and os.path.isfile(WIN_STARTUP_FILE):
                    os.remove(WIN_STARTUP_FILE)
            elif SYS_NAME == "Darwin":
                if os.path.isfile(MAC_PLIST_FILE):
                    os.remove(MAC_PLIST_FILE)
            else:
                if os.path.isfile(LINUX_AUTOSTART_FILE):
                    os.remove(LINUX_AUTOSTART_FILE)
                legacy_file = os.path.join(LINUX_AUTOSTART_DIR, "ubuntu-performance-track.desktop")
                if os.path.isfile(legacy_file):
                    os.remove(legacy_file)
            self.data["autostart"] = False
            self.save()
        except Exception as e:
            logging.error(f"Failed to remove autostart file: {e}")
