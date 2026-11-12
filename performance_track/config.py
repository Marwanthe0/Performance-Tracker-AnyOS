"""
config.py - Persistent configuration manager for Performance Track.
Saves and loads user preferences from ~/.config/ubuntu-performance-track/config.json.
Also handles autostart desktop entry creation/removal.
"""

import os
import json
import logging

CONFIG_DIR = os.path.expanduser("~/.config/ubuntu-performance-track")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
AUTOSTART_DIR = os.path.expanduser("~/.config/autostart")
AUTOSTART_FILE = os.path.join(AUTOSTART_DIR, "ubuntu-performance-track.desktop")

DEFAULT_CONFIG = {
    "update_interval": 2.0,
    "display_mode": "balanced",       # "balanced", "sparkline", "compact", "minimal", "detailed"
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
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            logging.error(f"Failed to save config to {CONFIG_FILE}: {e}")

    def sync_autostart(self, exec_path=None):
        """Enable or disable autostart desktop entry based on config."""
        autostart_enabled = self.get("autostart", False)
        if autostart_enabled:
            self.enable_autostart(exec_path)
        else:
            self.disable_autostart()

    def enable_autostart(self, exec_path=None):
        if not exec_path:
            exec_path = os.path.expanduser("~/.local/bin/ubuntu-performance-track")
            if not os.path.exists(exec_path):
                # Fallback to local python script
                exec_path = os.path.abspath(
                    os.path.join(os.path.dirname(__file__), "..", "run.sh")
                )

        os.makedirs(AUTOSTART_DIR, exist_ok=True)
        content = f"""[Desktop Entry]
Type=Application
Name=Ubuntu Performance Track
Comment=Live RAM, CPU, and Performance Tracking in Topbar
Exec={exec_path}
Icon=utilities-system-monitor
Terminal=false
Categories=System;Monitor;Utility;
StartupNotify=false
X-GNOME-Autostart-enabled=true
"""
        try:
            with open(AUTOSTART_FILE, "w", encoding="utf-8") as f:
                f.write(content)
            self.data["autostart"] = True
            self.save()
        except Exception as e:
            logging.error(f"Failed to write autostart desktop file: {e}")

    def disable_autostart(self):
        try:
            if os.path.isfile(AUTOSTART_FILE):
                os.remove(AUTOSTART_FILE)
            self.data["autostart"] = False
            self.save()
        except Exception as e:
            logging.error(f"Failed to remove autostart file: {e}")
